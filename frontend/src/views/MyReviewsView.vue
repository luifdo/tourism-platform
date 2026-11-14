<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { catalogUseCases, reviewUseCases } from '../composition'
import { useGestion } from '../ui/useGestion'
import { fmtDate, fmtMomento } from '../ui/format'
import EstadoCarga from '../components/shared/EstadoCarga.vue'
import Paginacion from '../components/shared/Paginacion.vue'
import Estrellas from '../components/reviews/Estrellas.vue'
import ResenaForm from '../components/reviews/ResenaForm.vue'

/* UC15 · Mis reseñas: los servicios que ya disfruté y aún no reseñé, y las que escribí (con su estado: publicada, en revisión u oculta). */
const { t, locale } = useI18n()
const { mensaje, sesionVencida } = useGestion()

const pendientes = ref([])
const mias = ref({ items: [], pagina: 1, tamano: 10, total: 0 })
const nombres = ref({})
const cargando = ref(true)
const error = ref('')
const abierto = ref(null) // { tipo: 'nueva', servicioId } | { tipo: 'editar', resena }
const aviso = ref('')

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try {
    const [p, m] = await Promise.all([reviewUseCases.pendientes(), reviewUseCases.misResenas({ pagina, tamano: 10, idioma: locale.value })])
    pendientes.value = p; mias.value = m
    const ids = [...p.map((x) => x.servicio_id), ...m.items.map((x) => x.servicio_id)]
    nombres.value = (await catalogUseCases.nombres(ids, { idioma: locale.value })).porId
  } catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'resenas') } finally { cargando.value = false }
}
onMounted(() => cargar())

const nombre = (id) => nombres.value[id]?.nombre ?? t('my.service')
const colorEstado = { PUBLICADA: 'bg-ok-bg text-ok', EN_REVISION: 'bg-warn-bg text-warn', OCULTA: 'bg-danger-bg text-danger' }
const vacio = computed(() => !pendientes.value.length && !mias.value.items.length)
async function guardada() { abierto.value = null; aviso.value = t('resenas.thanks'); await cargar(mias.value.pagina) }
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[860px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ t('resenas.kicker') }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,44px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('resenas.myTitle') }}</h1>
      <p class="mt-2 max-w-2xl text-muted">{{ t('resenas.myLead') }}</p>

      <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

      <div class="mt-8">
        <EstadoCarga :cargando="cargando" :error="error" :vacio="vacio" :texto-vacio="t('resenas.myEmpty')" alto="h-48" @reintentar="cargar()">
          <section v-if="pendientes.length" aria-labelledby="h-pend">
            <h2 id="h-pend" class="text-lg font-bold text-navy-darkest">{{ t('resenas.pending') }}</h2>
            <ul class="mt-3 space-y-3">
              <li v-for="p in pendientes" :key="p.servicio_id">
                <div v-if="abierto?.servicioId !== p.servicio_id" class="tarjeta flex flex-wrap items-center justify-between gap-3 !p-4">
                  <div><p class="font-semibold text-navy-darkest">{{ nombre(p.servicio_id) }}</p><p class="font-mono text-xs text-muted">{{ t('resenas.lastVisit', { fecha: fmtDate(p.ultima_visita, locale, { day: 'numeric', month: 'long', year: 'numeric' }) }) }}</p></div>
                  <button type="button" class="btn-primario" @click="abierto = { tipo: 'nueva', servicioId: p.servicio_id }; aviso = ''">{{ t('resenas.write') }}</button>
                </div>
                <ResenaForm v-else :servicio-id="p.servicio_id" @guardada="guardada" @cancelar="abierto = null" />
              </li>
            </ul>
          </section>

          <section v-if="mias.items.length" class="mt-10" aria-labelledby="h-mias">
            <h2 id="h-mias" class="text-lg font-bold text-navy-darkest">{{ t('resenas.mine') }}</h2>
            <ul class="mt-3 space-y-4">
              <li v-for="r in mias.items" :key="r.id">
                <ResenaForm v-if="abierto?.resena?.id === r.id" :servicio-id="r.servicio_id" :resena="r" @guardada="guardada" @cancelar="abierto = null" />
                <article v-else class="tarjeta">
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <Estrellas :valor="r.puntuacion" />
                    <RouterLink :to="{ name: 'service', params: { id: r.servicio_id } }" class="text-sm font-semibold text-navy underline hover:text-teal">{{ nombre(r.servicio_id) }}</RouterLink>
                    <span class="pildora" :class="colorEstado[r.estado]">{{ t(`resenas.states.${r.estado}`) }}</span>
                    <span class="font-mono text-xs text-muted">{{ fmtMomento(r.creada_en, locale, false) }}</span>
                  </div>
                  <p v-if="r.comentario" class="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-control">{{ r.comentario }}</p>
                  <p v-if="r.estado !== 'PUBLICADA'" class="mt-2 text-xs text-muted">{{ t(`resenas.stateHelp.${r.estado}`) }}</p>
                  <div v-if="r.respuesta" class="mt-3 rounded-xl bg-cream p-3 text-sm"><p class="font-mono text-[10px] uppercase tracking-[.12em] text-teal">{{ t('resenas.providerReply') }}</p><p class="mt-1 whitespace-pre-line text-ink-control">{{ r.respuesta.texto }}</p></div>
                  <button v-if="r.estado === 'PUBLICADA'" type="button" class="mt-3 text-sm font-medium text-navy underline hover:text-teal" @click="abierto = { tipo: 'editar', resena: r }; aviso = ''">{{ t('gestion.edit') }}</button>
                </article>
              </li>
            </ul>
            <Paginacion :pagina="mias.pagina" :tamano="mias.tamano" :total="mias.total" @cambiar="cargar" />
          </section>
        </EstadoCarga>
      </div>
    </div>
  </div>
</template>
