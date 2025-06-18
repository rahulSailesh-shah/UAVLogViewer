<template>
    <div id="app" style="height: 100%;">
        <router-view/>
        <FloatingButton />
    </div>
</template>

<script>
import FloatingButton from './components/FloatingButton.vue'

export default {
    name: 'App',
    components: {
        FloatingButton
    },
    data () {
        return {
            isConnected: false,
            clientId: null
        }
    },
    created () {
        // Generate a unique client ID
        this.clientId = 'client_' + Math.random().toString(36).substr(2, 9)
    },
    beforeDestroy () {
        // Cleanup will be handled by FloatingButton component
    }
}
</script>

<style>
@import url('https://fonts.googleapis.com/css?family=Nunito+Sans&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css');

#app {
    font-family: 'Nunito Sans', sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

html,
body {
    overscroll-behavior-y: contain;
}
</style>
