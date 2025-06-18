"use strict";
module.exports = {
    NODE_ENV: '"production"',
    VUE_APP_CESIUM_TOKEN: JSON.stringify(
        process.env.VUE_APP_CESIUM_TOKEN ||
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIwMTIzNmJhMy1jNDE3LTQ0MzAtODVkMS1mZmUzODdjMTg0MGIiLCJpZCI6MzAzNjYzLCJpYXQiOjE3NDc2MjEzOTR9.EuW7FIgBv2OzYDyy0xfCWiExKyLIK9S4qJoT4D5-qrM"
    )
};
