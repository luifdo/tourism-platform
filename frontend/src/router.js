import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import { authUseCases } from './composition'
import { rutaSegura } from './domain/auth/rules'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/servicios/:id', name: 'service', component: () => import('./views/ServiceView.vue'), props: true },
    { path: '/mis-reservas', name: 'my-bookings', component: () => import('./views/MyBookingsView.vue'), meta: { requiresAuth: true } },
    { path: '/ingresar', name: 'login', component: () => import('./views/LoginView.vue'), meta: { guestOnly: true } },
    { path: '/registro', name: 'register', component: () => import('./views/RegisterView.vue'), meta: { guestOnly: true } },
    { path: '/recuperar', name: 'recover', component: () => import('./views/RecoverView.vue'), meta: { guestOnly: true } },
    { path: '/restablecer-contrasena', name: 'reset', component: () => import('./views/ResetView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, _from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, top: 76, behavior: 'smooth' }
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const e = authUseCases.estado()
  // Sin conexión se permite ver lo ya guardado aunque el token haya vencido (solo lectura); enviar pendientes pedirá ingresar
  const puedeVerGuardado = !!e.usuario && typeof navigator !== 'undefined' && !navigator.onLine
  if (to.meta.requiresAuth && !e.autenticado && !puedeVerGuardado)
    return { name: 'login', query: { redirect: to.fullPath, ...(e.expirada ? { expirada: '1' } : {}) } }
  if (to.meta.guestOnly && e.autenticado) return { path: rutaSegura(to.query.redirect) }
})

export default router
