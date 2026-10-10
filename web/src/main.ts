import { createApp } from 'vue'
import App from './App.vue'
import { createPlayerRouter } from './router'
import './styles/tokens.css'
import './styles/app.css'

createApp(App).use(createPlayerRouter()).mount('#app')
