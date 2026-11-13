<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { offerUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { degradado } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import ServicioForm from './ServicioForm.vue'

/*
 * UC17 y UC18 · Mis servicios: lista (activos e inactivos), crear, editar, desactivar y reactivar.
 * Desactivar no borra: deja de mostrarse en el catálogo y se puede reactivar.
 */
const emit = defineEmits(['cambio'])
const { t, locale } = useI18n()
const { mensaje, sesionVencida } = useGestion()
const enLinea = useOnline()

const items = ref([])
const zonas = ref([])
const cargando = ref(true)
const error = ref('')
const modo = ref('lista') // 'lista' | 'nuevo' | 'editar'
const editado = ref(null)
const aviso = ref('')
const accion = ref({ id: '', error: '' })

async function cargar() {
  cargando.value = true; error.value = ''
  try {
    const [p, z] = await Promise.all([offerUseCases.servicios(), offerUseCases.zonas(locale.value).catch(() => [])])
    items.value = p.items; zonas.value = z
  } catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'oferta') } finally { cargando.value = false }
}
onMounted(cargar)

const nombre = (s) => (locale.value === 'en' && s.nombre.en ? s.nombre.en : s.nombre.es)
const nuevo = () => { aviso.value = ''; editado.value = null; modo.value = 'nuevo' }
const editar = (s) => { aviso.value = ''; editado.value = s; modo.value = 'editar' }
async function guardado(s) {
  aviso.value = t(modo.value === 'nuevo' ? 'oferta.created' : 'oferta.updated', { nombre: nombre(s) })
  modo.value = 'lista'; editado.value = null
  await cargar(); emit('cambio')
}

async function alternar(s) {
  accion.value = { id: s.id, error: '' }
  try {
    await (s.activo ? offerUseCases.desactivarServicio(s.id, s.version) : offerUseCases.reactivarServicio(s.id, s.version))
    aviso.value = t(s.activo ? 'oferta.deactivated' : 'oferta.reactivated', { nombre: nombre(s) })
    await cargar(); emit('cambio')
  } catch (e) {
    if (sesionVencida(e)) return
    accion.value = { id: s.id, error: e.code === 'VERSION_DISTINTA' ? t('oferta.errors.VERSION_DISTINTA') : mensaje(e, 'oferta') }
    if (e.code === 'VERSION_DISTINTA') await cargar()
  }
}
</script>

<template>
  <section aria-labelledby="h-servicios">
    <div v-if="modo === 'lista'" class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id="h-servicios" class="text-lg font-bold text-navy-darkest">{{ t('oferta.title') }}</h2>
        <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('oferta.lead') }}</p>
      </div>
      <button type="button" class="btn-primario" @click="nuevo">+ {{ t('oferta.new') }}</button>
    </div>
    <h2 v-else id="h-servicios" class="text-lg font-bold text-navy-darkest">{{ modo === 'nuevo' ? t('oferta.newTitle') : t('oferta.editTitle') }}</h2>

    <p v-if="aviso && modo === 'lista'" class="mt-3 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

    <div class="mt-4">
      <ServicioForm v-if="modo === 'nuevo'" :zonas="zonas" @guardado="guardado" @cancelar="modo = 'lista'" />
      <ServicioForm v-else-if="modo === 'editar'" :key="editado.id" :servicio="editado" :zonas="zonas" @guardado="guardado" @cancelar="modo = 'lista'" />

      <EstadoCarga v-else :cargando="cargando" :error="error" :vacio="!items.length" :texto-vacio="t('oferta.empty')" alto="h-40" @reintentar="cargar">
        <ul class="grid gap-4 sm:grid-cols-2">
          <li v-for="s in items" :key="s.id" class="tarjeta flex gap-4 !p-4" :class="{ 'opacity-75': !s.activo }">
            <div class="size-20 shrink-0 overflow-hidden rounded-xl" :style="{ background: degradado(s.categoria) }">
              <img v-if="s.imagenes_urls?.[0]" :src="s.imagenes_urls[0]" alt="" class="size-full object-cover" loading="lazy" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="flex flex-wrap items-center gap-2">
                <span class="truncate font-semibold text-navy-darkest">{{ nombre(s) }}</span>
                <span class="pildora" :class="s.activo ? 'bg-ok-bg text-ok' : 'bg-sand/20 text-ink-control'">{{ s.activo ? t('oferta.active') : t('oferta.inactive') }}</span>
              </p>
              <p class="mt-0.5 font-mono text-xs text-muted">{{ t(`oferta.opts.${s.tipo}`) }} · {{ s.zona?.nombre ?? '—' }}</p>
              <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <button type="button" class="font-medium text-navy underline hover:text-teal" @click="editar(s)">{{ t('gestion.edit') }}</button>
                <RouterLink v-if="s.activo" :to="{ name: 'service', params: { id: s.id } }" class="font-medium text-navy underline hover:text-teal">{{ t('oferta.view') }}</RouterLink>
                <button type="button" class="font-medium underline" :class="s.activo ? 'text-danger' : 'text-ok'" :disabled="!enLinea" @click="alternar(s)">{{ s.activo ? t('oferta.deactivate') : t('oferta.reactivate') }}</button>
              </div>
              <p v-if="accion.id === s.id && accion.error" class="campo-error" role="alert">{{ accion.error }}</p>
            </div>
          </li>
        </ul>
      </EstadoCarga>
    </div>
  </section>
</template>
