<template>
    <div class="floating-button-container">
        <button id="floating-chat-button" class="floating-button" @click="toggleChat">
            <i class="fas fa-comments"></i>
            <span v-if="!isConnected" class="connection-status disconnected"></span>
            <span v-else class="connection-status connected"></span>
        </button>

        <!-- Modal -->
        <div v-if="isOpen" class="chat-modal">
            <div class="chat-header">
                <h3>Chat</h3>
                <button @click="toggleChat" class="close-button">&times;</button>
            </div>

            <div class="chat-messages" ref="messagesContainer">
                <div v-for="(message, index) in messages" :key="index" :class="['message', message.type]">
                    <div class="message-content">{{ message.content }}</div>
                    <div class="message-timestamp">{{ formatTimestamp(message.timestamp) }}</div>
                </div>
                <div v-if="isProcessingQuestion" class="message server processing-message">
                    <div class="message-content">
                        <div class="loading-indicator">
                            <div class="loading-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                            <div class="loading-text">Processing your question...</div>
                        </div>
                    </div>
                    <div class="message-timestamp">{{ formatTimestamp(new Date().toISOString()) }}</div>
                </div>
                <div v-if="isUploadingFile" class="message system">
                    <div class="message-content">
                        <div class="loading-indicator">
                            <div class="loading-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                            <div class="loading-text">Processing File...</div>
                        </div>
                    </div>
                    <div class="message-timestamp">{{ formatTimestamp(new Date().toISOString()) }}</div>
                </div>

            </div>

            <div class="chat-input">
                <input
                    type="text"
                    v-model="newMessage"
                    @keyup.enter="sendMessage"
                    placeholder="Type a message..."
                >
                <button @click="sendMessage" :disabled="!newMessage.trim()">Send</button>
            </div>
        </div>
    </div>
</template>

<script>
import { store } from './Globals'

export default {
    name: 'FloatingButton',
    data () {
        return {
            isOpen: false,
            newMessage: '',
            messages: [],
            hasFile: false,
            isConnected: false,
            parsedData: null,
            ws: null,
            clientId: null,
            reconnectAttempts: 0,
            maxReconnectAttempts: 5,
            reconnectDelay: 5000,
            chunkSize: 1024 * 1024,
            currentFile: null,
            isSendingFile: false,
            isChatEnabled: true,
            isProcessingQuestion: false,
            isUploadingFile: false,
            isProcessingFile: false
        }
    },
    created () {
        // Listen for file upload events
        this.$eventHub.$on('messagesDoneLoading', this.onFileLoaded)
        this.$eventHub.$on('file-ready', this.setCurrentFile)
        // Listen for WebSocket events
        this.$eventHub.$on('websocket-message', this.onMessageReceived)
        this.$eventHub.$on('websocket-error', this.onMessageReceived)
    },
    beforeDestroy () {
        this.$eventHub.$off('messagesDoneLoading')
        this.$eventHub.$off('file-ready')
        this.$eventHub.$off('websocket-message')
        this.$eventHub.$off('websocket-error')
        this.disconnectWebSocket()
    },
    methods: {
        async connectWebSocket () {
            // Don't create a new connection if one already exists and is open
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                console.log('WebSocket already connected')
                return
            }

            // Generate a unique client ID if not already set
            if (!this.clientId) {
                this.clientId = 'client_' + Math.random().toString(36).substr(2, 9)
            }

            console.log('Attempting to connect WebSocket...')

            return new Promise((resolve, reject) => {
                this.ws = new WebSocket(`ws://0.0.0.0:8000/ws/${this.clientId}`)

                this.ws.onopen = () => {
                    console.log('WebSocket connected successfully')
                    this.isConnected = true
                    this.reconnectAttempts = 0
                    // Don't add connection message to chat anymore
                    resolve()
                }

                this.ws.onmessage = (event) => {
                    console.log('WebSocket message received:', event.data)
                    try {
                        const data = JSON.parse(event.data)
                        this.onMessageReceived(data)
                    } catch (error) {
                        console.error('Error parsing WebSocket message:', error)
                    }
                }

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error)
                    this.isConnected = false
                    this.messages.push({
                        type: 'system',
                        content: 'Error connecting to chat server',
                        timestamp: new Date().toISOString()
                    })
                    reject(error)
                }

                this.ws.onclose = () => {
                    console.log('WebSocket connection closed')
                    this.isConnected = false

                    // Only attempt to reconnect if we haven't exceeded max attempts
                    if (this.reconnectAttempts < this.maxReconnectAttempts) {
                        this.reconnectAttempts++
                        console.log(`Attempting to reconnect WebSocket
                        (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
                        setTimeout(() => {
                            this.connectWebSocket()
                        }, this.reconnectDelay)
                    } else {
                        console.log('Max reconnection attempts reached')
                        this.messages.push({
                            type: 'system',
                            content: 'Failed to reconnect to chat server after multiple attempts',
                            timestamp: new Date().toISOString()
                        })
                    }
                }
            })
        },
        async onFileLoaded () {
            console.log('onFileLoaded called')
            this.hasFile = true
            this.updateParsedData()

            try {
                // Wait for WebSocket connection to be established
                await this.connectWebSocket()
                console.log('WebSocket connected', this.isConnected, this.currentFile)

                // Start sending file chunks after connection is established
                if (this.isConnected && this.currentFile) {
                    console.log('Sending file chunks')
                    await this.sendFileChunks()
                } else {
                    console.error('Cannot send file: WebSocket not connected or no file available')
                }
            } catch (error) {
                console.error('Error establishing WebSocket connection:', error)
                this.messages.push({
                    type: 'system',
                    content: 'Failed to establish WebSocket connection',
                    timestamp: new Date().toISOString()
                })
            }
        },
        disconnectWebSocket () {
            if (this.ws) {
                // Only close if we're actually connected
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.close()
                }
                this.ws = null
                this.isConnected = false
            }
        },
        updateParsedData () {
            // Get the latest trajectory data
            const trajectorySource = store.trajectorySource
            const trajectory = store.trajectories[trajectorySource]

            // Get the latest attitude data
            let attitude = null
            if (store.timeAttitude && Object.keys(store.timeAttitude).length > 0) {
                const latestTime = Math.max(...Object.keys(store.timeAttitude))
                const [roll, pitch, yaw] = store.timeAttitude[latestTime]
                attitude = { roll, pitch, yaw }
            } else if (store.timeAttitudeQ && Object.keys(store.timeAttitudeQ).length > 0) {
                // Convert quaternion to euler angles if needed
                const latestTime = Math.max(...Object.keys(store.timeAttitudeQ))
                const [q1, q2, q3, q4] = store.timeAttitudeQ[latestTime]
                // Convert quaternion to euler angles
                const roll = Math.atan2(2 * (q1 * q2 + q3 * q4), 1 - 2 * (q2 * q2 + q3 * q3))
                const pitch = Math.asin(2 * (q1 * q3 - q4 * q2))
                const yaw = Math.atan2(2 * (q1 * q4 + q2 * q3), 1 - 2 * (q3 * q3 + q4 * q4))
                attitude = { roll, pitch, yaw }
            }

            // Get parameters
            const parameters = []
            if (store.params) {
                for (const [name, value] of Object.entries(store.params)) {
                    parameters.push({ name, value })
                }
            }

            // Update the parsed data
            this.parsedData = {
                trajectory: trajectory
                    ? trajectory.trajectory.map(point => ({
                        lat: point[1],
                        lng: point[0],
                        alt: point[2]
                    }))
                    : [],
                attitude,
                parameters
            }

            // Send the data to the backend
            this.sendDataToBackend({
                type: 'parsed_data',
                data: this.parsedData
            })
        },
        sendMessage () {
            if (!this.newMessage.trim() || !this.isConnected || !this.ws) {
                console.warn('Cannot send message: WebSocket not connected')
                return
            }

            // Reset processing state when sending a new message
            this.isProcessingQuestion = false

            const message = {
                type: 'chat',
                content: this.newMessage,
                timestamp: new Date().toISOString()
            }

            // Add message to local chat immediately
            this.messages.push({
                type: 'user',
                content: this.newMessage,
                timestamp: new Date().toISOString()
            })

            try {
                // Send to WebSocket server
                this.ws.send(JSON.stringify(message))
                this.newMessage = ''

                // Scroll to bottom after adding message
                this.scrollToBottom()
            } catch (error) {
                console.error('Error sending message:', error)
                this.messages.push({
                    type: 'system',
                    content: 'Failed to send message. Please try again.',
                    timestamp: new Date().toISOString()
                })
            }
        },
        scrollToBottom () {
            this.$nextTick(() => {
                const container = this.$refs.messagesContainer
                if (container) {
                    container.scrollTop = container.scrollHeight
                }
            })
        },
        async sendDataToBackend (data) {
            console.log('sendDataToBackend called with data:', data)
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                console.error('WebSocket not connected. Current state:', this.ws?.readyState)
                return
            }

            try {
                const message = {
                    type: 'data',
                    content: data,
                    timestamp: new Date().toISOString()
                }
                console.log('Sending data to backend:', message)
                this.ws.send(JSON.stringify(message))
            } catch (error) {
                console.error('Error sending data to backend:', error)
            }
        },
        onMessageReceived (message) {
            console.log('Processing message:', message)
            // Handle different message types
            switch (message.type) {
            case 'chat':
                // Check if this is the "Processing your question..." message
                if (message.content === 'Processing your question...') {
                    this.isProcessingQuestion = true
                } else {
                    // If we were processing a question, stop the loading indicator
                    this.isProcessingQuestion = false
                    this.messages.push({
                        type: 'server',
                        content: message.content,
                        timestamp: message.timestamp
                    })
                }
                break
            case 'system':
                // Filter out connection messages
                if (message.content === 'Connected to chat server' ||
                    message.content.startsWith('Welcome! Your client ID is:')) {
                    // Don't show these messages in chat
                    break
                }

                // Filter out "Processing File" message
                if (message.content === 'Processing File') {
                    // Don't show this message in chat as it's just a status update
                    break
                }

                // Check if this is the file processing success message
                if (message.content.startsWith('Log file processed successfully:')) {
                    this.isProcessingFile = false
                    this.isUploadingFile = false
                    this.isProcessingQuestion = false // Also remove any question processing indicator
                    // Don't show this message in chat as it's just a status update
                    break
                }

                // Check if this is the file saved message
                if (message.content.startsWith('File saved successfully:')) {
                    this.isUploadingFile = false
                    this.isProcessingFile = true
                    // Don't show this message in chat as it's just a status update
                    break
                }

                // Show other system messages
                this.messages.push({
                    type: 'system',
                    content: message.content,
                    timestamp: message.timestamp
                })
                break
            case 'acknowledgment':
                console.log('Received acknowledgment:', message.content)
                break
            case 'error':
                // Stop all processing indicators if there's an error
                this.isProcessingQuestion = false
                this.isUploadingFile = false
                this.isProcessingFile = false
                console.error('WebSocket error:', message.content)
                this.messages.push({
                    type: 'system',
                    content: `Error: ${message.content}`,
                    timestamp: message.timestamp
                })
                break
            default:
                console.log('Unknown message type:', message.type)
            }

            this.scrollToBottom()
        },
        formatTimestamp (timestamp) {
            if (!timestamp) return ''
            const date = new Date(timestamp)
            return date.toLocaleTimeString()
        },
        async sendFileChunks () {
            if (!this.currentFile) {
                console.error('No file to send')
                return
            }

            try {
                this.isSendingFile = true
                this.isChatEnabled = false
                this.isUploadingFile = true
                const chunkSize = 1024 * 1024 // 1MB chunks
                const totalChunks = Math.ceil(this.currentFile.size / chunkSize)
                console.log(`Sending file in ${totalChunks} chunks`)

                for (let i = 0; i < totalChunks; i++) {
                    const start = i * chunkSize
                    const end = Math.min(start + chunkSize, this.currentFile.size)
                    const chunk = this.currentFile.slice(start, end)

                    const reader = new FileReader()
                    const chunkPromise = new Promise((resolve, reject) => {
                        reader.onload = async (e) => {
                            try {
                                const base64Data = e.target.result.split(',')[1]
                                const message = {
                                    type: 'file_chunk',
                                    content: {
                                        chunkIndex: i,
                                        totalChunks: totalChunks,
                                        fileName: this.currentFile.name,
                                        data: base64Data
                                    }
                                }
                                console.log(`Sending chunk ${i + 1}/${totalChunks}`)
                                this.ws.send(JSON.stringify(message))
                                resolve()
                            } catch (error) {
                                reject(error)
                            }
                        }
                        reader.onerror = reject
                    })

                    reader.readAsDataURL(chunk)
                    await chunkPromise
                    await new Promise(resolve => setTimeout(resolve, 100)) // Small delay between chunks
                }

                // Send completion message
                const completeMessage = {
                    type: 'file_complete',
                    content: {
                        fileName: this.currentFile.name,
                        totalChunks: totalChunks
                    }
                }
                console.log('Sending file complete message')
                this.ws.send(JSON.stringify(completeMessage))
                this.currentFile = null
            } catch (error) {
                console.error('Error sending file chunks:', error)
                this.messages.push({
                    type: 'error',
                    content: 'Error sending file: ' + error.message,
                    timestamp: new Date().toISOString()
                })
                this.isChatEnabled = true
                this.isUploadingFile = false
            } finally {
                this.isSendingFile = false
            }
        },
        readChunkAsArrayBuffer (chunk) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader()
                reader.onload = () => resolve(reader.result)
                reader.onerror = reject
                reader.readAsArrayBuffer(chunk)
            })
        },
        setCurrentFile (file) {
            this.currentFile = file
        },
        onMessage (event) {
            try {
                const message = JSON.parse(event.data)
                console.log('Received message:', message)

                if (message.type === 'error') {
                    this.isChatEnabled = false
                    this.messages.push(message)
                } else {
                    // Enable chat for all non-error messages
                    this.isChatEnabled = true
                    this.messages.push(message)
                }
            } catch (error) {
                console.error('Error parsing message:', error)
            }
        },
        toggleChat () {
            this.isOpen = !this.isOpen
        }
    }
}
</script>

<style scoped>
.floating-button-container {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1000;
}

.floating-button {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background-color: rgb(33, 41, 61);
    color: white;
    border: 1px solid rgba(91, 100, 117, 0.76);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    transition: all 0.3s ease;
}

.floating-button:hover {
    transform: scale(1.1);
    background-color: rgb(47, 58, 87);
    box-shadow: 0px 0px 12px 0px rgba(37, 78, 133, 0.55);
}

.connection-status {
    position: absolute;
    top: -5px;
    right: -5px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.connection-status.connected {
    background-color: rgb(38, 53, 71);
}

.connection-status.disconnected {
    background-color: #f44336;
}

.chat-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 90%;
    height: 90%;
    max-width: 1200px;
    max-height: 800px;
    background: rgba(253, 254, 255, 0.856);
    color: #141924;
    border-radius: 10px;
    box-shadow: 9px 9px 3px -6px rgba(26, 26, 26, 0.699);
    display: flex;
    flex-direction: column;
    z-index: 1000;
}

.chat-header {
    padding: 20px;
    background: rgb(33, 41, 61);
    color: white;
    border-radius: 10px 10px 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(91, 100, 117, 0.76);
}

.chat-header h3 {
    margin: 0;
    font-size: 1.4em;
    font-weight: 600;
    text-transform: uppercase;
}

.close-button {
    background: none;
    border: none;
    color: white;
    font-size: 24px;
    cursor: pointer;
    padding: 0;
    line-height: 1;
    transition: all 0.3s ease;
}

.close-button:hover {
    color: rgba(255, 255, 255, 0.8);
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 15px;
    background: rgba(253, 254, 255, 0.856);
}

.message {
    max-width: 70%;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 5px;
    font-size: 1.1em;
    border: 1px solid rgba(91, 100, 117, 0.76);
}

.message.system {
    background-color: rgb(33, 41, 61);
    color: white;
    align-self: center;
}

.message.error {
    background-color: #f44336;
    color: white;
    align-self: center;
}

.message.user {
    background-color: rgb(38, 53, 71);
    color: white;
    align-self: flex-end;
}

.message.server {
    background-color: rgba(253, 254, 255, 0.856);
    color: #141924;
    border: 1px solid rgba(91, 100, 117, 0.76);
    align-self: flex-start;
}

.message-timestamp {
    font-size: 0.7em;
    color: rgba(91, 100, 117, 0.76);
    margin-top: 5px;
}

.chat-input {
    padding: 20px;
    border-top: 1px solid rgba(91, 100, 117, 0.76);
    display: flex;
    gap: 15px;
    background: rgba(253, 254, 255, 0.856);
}

.chat-input input {
    flex: 1;
    padding: 15px;
    border: 1px solid rgba(91, 100, 117, 0.76);
    border-radius: 8px;
    font-size: 1.1em;
    background: white;
    color: #141924;
}

.chat-input input:focus {
    outline: none;
    border-color: rgb(38, 53, 71);
    box-shadow: 0px 0px 12px 0px rgba(37, 78, 133, 0.15);
}

.chat-input input:disabled {
    background-color: rgba(91, 100, 117, 0.1);
    cursor: not-allowed;
}

.chat-input button {
    padding: 15px 30px;
    background: rgb(33, 41, 61);
    color: white;
    border: 1px solid rgba(91, 100, 117, 0.76);
    border-radius: 8px;
    cursor: pointer;
    font-size: 1.1em;
    min-width: 100px;
    transition: all 0.3s ease;
}

.chat-input button:hover:not(:disabled) {
    background-color: rgb(47, 58, 87);
    box-shadow: 0px 0px 12px 0px rgba(37, 78, 133, 0.55);
}

.chat-input button:disabled {
    background-color: rgba(91, 100, 117, 0.3);
    cursor: not-allowed;
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
    width: 12px;
    background-color: rgba(0, 0, 0, 0);
}

.chat-messages::-webkit-scrollbar-thumb {
    border-radius: 5px;
    box-shadow: inset 0 0 6px rgba(0, 0, 0, 0.1);
    background: rgb(60, 75, 112);
    background: linear-gradient(0deg, rgb(67, 95, 155) 51%, rgb(61, 79, 121) 100%);
}

/* Loading indicator styles */
.loading-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
}

.loading-dots {
    display: flex;
    gap: 4px;
    align-items: center;
}

.loading-dots span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: rgb(38, 53, 71);
    animation: loading-dots 1.4s ease-in-out infinite both;
}

.loading-dots span:nth-child(1) {
    animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
    animation-delay: -0.16s;
}

.loading-dots span:nth-child(3) {
    animation-delay: 0s;
}

@keyframes loading-dots {
    0%, 80%, 100% {
        transform: scale(0.8);
        opacity: 0.5;
    }
    40% {
        transform: scale(1);
        opacity: 1;
    }
}

.loading-text {
    font-size: 0.9em;
    color: rgba(91, 100, 117, 0.8);
    font-style: italic;
}

.processing-message {
    background-color: rgba(253, 254, 255, 0.9) !important;
    border: 1px solid rgba(91, 100, 117, 0.4) !important;
}
</style>
