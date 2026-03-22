import { createRouter, createWebHistory } from 'vue-router'
import CheckPage from '../views/CheckPage.vue'
import ResultPage from '../views/ResultPage.vue'
import RuleConfig from '../views/RuleConfig.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: CheckPage },
    { path: '/result/:taskId', component: ResultPage },
    { path: '/rules', component: RuleConfig },
  ],
})

export default router
