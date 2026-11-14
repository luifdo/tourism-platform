import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import { authUseCases } from './composition'
import { rutaSegura } from './domain/auth/rules'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/servicios/:id', name: 'service', component: () => import('./views/ServiceView.vue'), props: true },
    { path: '/mis-reservas', name: 'my-bookings', component: () => import('./views/MyBookingsView.vue'), meta: { requiresAuth: true, roles: ['Turista'] } },
    { path: '/mis-resenas', name: 'my-reviews', component: () => import('./views/MyReviewsView.vue'), meta: { requiresAuth: true, roles: ['Turista'] } },
    { path: '/perfil', name: 'profile', component: () => import('./views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/entidad', name: 'entity', component: () => import('./views/EntityView.vue'), meta: { requiresAuth: true, roles: ['Entidad', 'Admin'] } },
    { path: '/admin', name: 'admin', component: () => import('./views/AdminView.vue'), meta: { requiresAuth: true, roles: ['Admin'] } },
    { path: '/prestador', name: 'provider', component: () => import('./views/ProviderView.vue'), meta: { requiresAuth: true, roles: ['Prestador'] } },
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
  // Una pantalla de un rol (el panel del prestador, de la Entidad, del Admin) no la abre quien tiene otro: el servicio igual respondería 403
  if (to.meta.roles && e.usuario && !to.meta.roles.includes(e.usuario.rol)) return { name: 'home', query: { sinpermiso: '1' } } // y la portada avisa por qué (App.vue)
})

export default router
