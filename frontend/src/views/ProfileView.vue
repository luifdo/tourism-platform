<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { accountUseCases } from '../composition'
import { evaluarPassword } from '../domain/auth/rules'
import { useGestion } from '../ui/useGestion'
import { useSession } from '../ui/useSession'
import { useOnline } from '../ui/useOnline'
import EstadoCarga from '../components/shared/EstadoCarga.vue'

/*
 * UC4 · Mi perfil: datos, cambio de contraseña y supresión de la cuenta (Ley 1581 de 2012, habeas data).
 * Cambiar la contraseña revoca todas las sesiones: hay que ingresar de nuevo. Suprimir los datos es irreversible.
 */
const { t, locale } = useI18n()
const router = useRouter()
const { expirar } = useSession()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const perfil = ref(null)
const cargando = ref(true)
const errorCarga = ref('')

const datos = reactive({ nombre: '', idioma: 'es', guardando: false, ok: false, error: '', campos: {} })
const clave = reactive({ actual: '', nueva: '', confirmacion: '', ver: false, enviando: false, error: '', campos: {} })
const baja = reactive({ abierta: false, password: '', confirmo: false, enviando: false, error: '', campos: {} })
const reglas = () => evaluarPassword(clave.nueva)

async function cargar() {
  cargando.value = true; errorCarga.value = ''
  try {
    perfil.value = await accountUseCases.perfil()
    datos.nombre = perfil.value.nombre; datos.idioma = perfil.value.idioma
  } catch (e) { if (!sesionVencida(e)) errorCarga.value = mensaje(e, 'perfil') } finally { cargando.value = false }
}
onMounted(cargar)

function aplicarIdioma(l) {
  locale.value = l
  document.documentElement.lang = l
  try { localStorage.setItem('lang', l) } catch { /* sin almacenamiento */ }
}

async function guardar() {
  datos.guardando = true; datos.ok = false; datos.error = ''; datos.campos = {}
  try {
    const cambios = {}
    if (datos.nombre.trim() !== perfil.value.nombre) cambios.nombre = datos.nombre
    if (datos.idioma !== perfil.value.idioma) cambios.idioma = datos.idioma
    perfil.value = await accountUseCases.editarPerfil(cambios)
    if (cambios.idioma) aplicarIdioma(cambios.idioma)
    datos.ok = true
  } catch (e) {
    if (sesionVencida(e)) return
    datos.error = mensaje(e, 'perfil'); datos.campos = camposDe(e)
  } finally { datos.guardando = false }
}

async function cambiarClave() {
  clave.enviando = true; clave.error = ''; clave.campos = {}
  try {
    await accountUseCases.cambiarContrasena({ actual: clave.actual, nueva: clave.nueva, confirmacion: clave.confirmacion })
    // El servicio revocó todas las sesiones, también esta. App.vue manda a ingresar («tu sesión expiró») cuando la sesión vence en
    // una pantalla protegida; aquí el motivo es otro, así que se espera a que ese aviso salga y se navega después, con el nuestro.
    expirar()
    await nextTick()
    router.replace({ name: 'login', query: { clave: '1' } })
  } catch (e) {
    if (sesionVencida(e)) return
    clave.error = mensaje(e, 'perfil'); clave.campos = camposDe(e)
  } finally { clave.enviando = false }
}

async function suprimir() {
  baja.enviando = true; baja.error = ''; baja.campos = {}
  try {
    await accountUseCases.suprimirDatos(baja.password)
    expirar()
    await nextTick() // ver cambiarClave: el aviso global de sesión vencida no debe ganarle a este destino
    router.replace({ name: 'home' })
  } catch (e) {
    if (sesionVencida(e)) return
    baja.error = mensaje(e, 'perfil'); baja.campos = camposDe(e)
  } finally { baja.enviando = false }
}
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[760px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ t('perfil.kicker') }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,44px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('perfil.title') }}</h1>
      <p class="mt-2 max-w-xl text-muted">{{ t('perfil.lead') }}</p>

      <div class="mt-8">
        <EstadoCarga :cargando="cargando" :error="errorCarga" alto="h-64" @reintentar="cargar">
          <template v-if="perfil">
            <!-- Datos -->
            <form class="tarjeta" aria-labelledby="h-datos" @submit.prevent="guardar">
              <h2 id="h-datos" class="text-lg font-bold text-navy-darkest">{{ t('perfil.data') }}</h2>
              <dl class="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                <div><dt class="campo-etiqueta">{{ t('perfil.email') }}</dt><dd class="mt-1 break-all text-ink-control">{{ perfil.email }}</dd></div>
                <div><dt class="campo-etiqueta">{{ t('perfil.role') }}</dt><dd class="mt-1"><span class="pildora bg-teal/15 text-teal">{{ t(`perfil.roles.${perfil.rol}`) }}</span></dd></div>
                <div v-if="perfil.razon_social" class="sm:col-span-2"><dt class="campo-etiqueta">{{ t('perfil.businessName') }}</dt><dd class="mt-1 text-ink-control">{{ perfil.razon_social }}</dd></div>
              </dl>
              <div class="mt-4 grid gap-4 sm:grid-cols-2">
                <label><span class="campo-etiqueta">{{ t('perfil.name') }}</span>
                  <input v-model="datos.nombre" class="campo-input" maxlength="100" autocomplete="name" required :aria-invalid="!!datos.campos.nombre" />
                  <span v-if="datos.campos.nombre" class="campo-error">{{ datos.campos.nombre }}</span>
                </label>
                <label><span class="campo-etiqueta">{{ t('perfil.language') }}</span>
                  <select v-model="datos.idioma" class="campo-input"><option value="es">Español</option><option value="en">English</option></select>
                </label>
              </div>
              <p v-if="datos.error" class="campo-error" role="alert">{{ datos.error }}</p>
              <p v-if="datos.ok" class="mt-3 text-sm text-ok" role="status">{{ t('perfil.saved') }}</p>
              <button type="submit" class="btn-primario mt-4" :disabled="datos.guardando || !enLinea">{{ datos.guardando ? t('gestion.saving') : t('gestion.save') }}</button>
              <p v-if="!enLinea" class="mt-2 text-xs text-muted">{{ t('gestion.needOnline') }}</p>
            </form>

            <!-- Contraseña -->
            <form class="tarjeta mt-6" aria-labelledby="h-clave" @submit.prevent="cambiarClave">
              <h2 id="h-clave" class="text-lg font-bold text-navy-darkest">{{ t('perfil.password') }}</h2>
              <p class="mt-1 text-sm text-muted">{{ t('perfil.passwordNote') }}</p>
              <div class="mt-4 grid gap-4 sm:grid-cols-2">
                <label class="sm:col-span-2"><span class="campo-etiqueta">{{ t('perfil.currentPassword') }}</span>
                  <input v-model="clave.actual" :type="clave.ver ? 'text' : 'password'" class="campo-input" autocomplete="current-password" required :aria-invalid="!!clave.campos.actual" />
                  <span v-if="clave.campos.actual" class="campo-error">{{ clave.campos.actual }}</span>
                </label>
                <label><span class="campo-etiqueta">{{ t('perfil.newPassword') }}</span>
                  <input v-model="clave.nueva" :type="clave.ver ? 'text' : 'password'" class="campo-input" autocomplete="new-password" required aria-describedby="reglas-clave" :aria-invalid="!!clave.campos.nueva" />
                  <span v-if="clave.campos.nueva" class="campo-error">{{ clave.campos.nueva }}</span>
                </label>
                <label><span class="campo-etiqueta">{{ t('perfil.confirmPassword') }}</span>
                  <input v-model="clave.confirmacion" :type="clave.ver ? 'text' : 'password'" class="campo-input" autocomplete="new-password" required :aria-invalid="!!clave.campos.confirmacion" />
                  <span v-if="clave.campos.confirmacion" class="campo-error">{{ clave.campos.confirmacion }}</span>
                </label>
              </div>
              <ul id="reglas-clave" class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs">
                <li v-for="r in ['longitud', 'letra', 'numero']" :key="r" :class="reglas()[r] ? 'text-ok' : 'text-muted'">{{ reglas()[r] ? '✓' : '○' }} {{ t(`perfil.rules.${r}`) }}</li>
              </ul>
              <label class="mt-3 flex items-center gap-2 text-sm text-ink-control"><input v-model="clave.ver" type="checkbox" class="size-4 accent-navy" />{{ t('perfil.showPasswords') }}</label>
              <p v-if="clave.error" class="campo-error" role="alert">{{ clave.error }}</p>
              <button type="submit" class="btn-primario mt-4" :disabled="clave.enviando || !enLinea">{{ clave.enviando ? t('gestion.saving') : t('perfil.changePassword') }}</button>
            </form>

            <!-- Supresión de datos -->
            <section class="tarjeta mt-6 border-danger/30" aria-labelledby="h-baja">
              <h2 id="h-baja" class="text-lg font-bold text-danger">{{ t('perfil.deleteTitle') }}</h2>
              <p class="mt-1 text-sm leading-relaxed text-ink-control">{{ t('perfil.deleteBody') }}</p>
              <button v-if="!baja.abierta" type="button" class="btn-peligro mt-4" @click="baja.abierta = true">{{ t('perfil.deleteStart') }}</button>
              <form v-else class="mt-4 space-y-3" @submit.prevent="suprimir">
                <label class="block"><span class="campo-etiqueta">{{ t('perfil.deletePassword') }}</span>
                  <input v-model="baja.password" type="password" class="campo-input" autocomplete="current-password" required :aria-invalid="!!baja.campos.password" />
                  <span v-if="baja.campos.password" class="campo-error">{{ baja.campos.password }}</span>
                </label>
                <label class="flex items-start gap-2 text-sm text-ink-control"><input v-model="baja.confirmo" type="checkbox" class="mt-0.5 size-4 accent-danger" />{{ t('perfil.deleteConfirm') }}</label>
                <p v-if="baja.error" class="campo-error" role="alert">{{ baja.error }}</p>
                <div class="flex flex-wrap gap-3">
                  <button type="submit" class="btn-peligro" :disabled="!baja.confirmo || !baja.password || baja.enviando || !enLinea">{{ baja.enviando ? t('gestion.saving') : t('perfil.deleteGo') }}</button>
                  <button type="button" class="btn-secundario" @click="baja.abierta = false; baja.password = ''; baja.confirmo = false">{{ t('gestion.cancel') }}</button>
                </div>
              </form>
            </section>
          </template>
        </EstadoCarga>
      </div>
    </div>
  </div>
</template>
