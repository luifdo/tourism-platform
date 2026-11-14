<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { accountUseCases } from '../../composition'
import { MAX_DOCUMENTO_BYTES } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'

/*
 * UC37 · Verificación del prestador: sube el RNT (Registro Nacional de Turismo) y el RUT. Mientras el Admin no apruebe
 * ambos, la cuenta no puede publicar ofertas. Un documento aprobado no se reemplaza; uno rechazado sí, con el motivo a la vista.
 */
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const estado = ref(null)
const cargando = ref(true)
const errorCarga = ref('')
const TIPOS = ['RNT', 'RUT']
const formularios = reactive({ RNT: nuevo(), RUT: nuevo() })
function nuevo() { return { archivo: null, razonSocial: '', enviando: false, error: '', campos: {}, ok: false } }

const doc = (tipo) => estado.value?.documentos.find((d) => d.tipo_documento === tipo) ?? null
const colorEstado = { Pendiente: 'bg-warn-bg text-warn', Aprobado: 'bg-ok-bg text-ok', Rechazado: 'bg-danger-bg text-danger' }
const kb = (b) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)
const maxMb = MAX_DOCUMENTO_BYTES / 1024 / 1024
const puedeSubir = (tipo) => doc(tipo)?.estado !== 'Aprobado'
const razonGuardada = computed(() => estado.value?.razon_social ?? '')

async function cargar() {
  cargando.value = true; errorCarga.value = ''
  try {
    estado.value = await accountUseCases.misDocumentos()
    if (!formularios.RUT.razonSocial) formularios.RUT.razonSocial = razonGuardada.value
  } catch (e) { if (!sesionVencida(e)) errorCarga.value = mensaje(e, 'verif') } finally { cargando.value = false }
}
onMounted(cargar)

const elegir = (tipo, e) => { formularios[tipo].archivo = e.target.files?.[0] ?? null; formularios[tipo].error = ''; formularios[tipo].campos = {}; formularios[tipo].ok = false }

async function subir(tipo) {
  const f = formularios[tipo]
  f.enviando = true; f.error = ''; f.campos = {}; f.ok = false
  try {
    await accountUseCases.subirDocumento({ tipo, archivo: f.archivo, razonSocial: f.razonSocial })
    f.archivo = null; f.ok = true
    await cargar()
  } catch (e) {
    if (sesionVencida(e)) return
    f.error = mensaje(e, 'verif'); f.campos = camposDe(e)
  } finally { f.enviando = false }
}
</script>

<template>
  <section aria-labelledby="h-verif">
    <h2 id="h-verif" class="text-lg font-bold text-navy-darkest">{{ t('verif.title') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('verif.lead') }}</p>

    <div class="mt-4">
      <EstadoCarga :cargando="cargando" :error="errorCarga" alto="h-40" @reintentar="cargar">
        <template v-if="estado">
          <p class="flex flex-wrap items-center gap-2 text-sm">
            <span class="campo-etiqueta">{{ t('verif.status') }}</span>
            <span class="pildora" :class="{ aprobado: 'bg-ok-bg text-ok', pendiente: 'bg-warn-bg text-warn', rechazado: 'bg-danger-bg text-danger', incompleto: 'bg-sand/15 text-ink-control' }[estado.estado]">{{ t(`verif.states.${estado.estado}`) }}</span>
          </p>
          <p class="mt-2 text-sm text-ink-control">{{ t(`verif.help.${estado.estado}`) }}</p>

          <div class="mt-5 grid gap-4 sm:grid-cols-2">
            <article v-for="tipo in TIPOS" :key="tipo" class="tarjeta" :aria-labelledby="`doc-${tipo}`">
              <h3 :id="`doc-${tipo}`" class="font-mono text-[11px] uppercase tracking-[.14em] text-teal">{{ t(`verif.docs.${tipo}`) }}</h3>
              <p class="mt-1 text-xs text-muted">{{ t(`verif.docsHint.${tipo}`) }}</p>

              <div v-if="doc(tipo)" class="mt-3 rounded-xl bg-cream p-3 text-sm">
                <span class="pildora" :class="colorEstado[doc(tipo).estado]">{{ t(`verif.docStates.${doc(tipo).estado}`) }}</span>
                <p class="mt-1.5 text-xs text-muted">{{ t('verif.uploaded', { fecha: fmtMomento(doc(tipo).fecha_subida, locale, false), tam: kb(doc(tipo).tamano_bytes) }) }}</p>
                <p v-if="doc(tipo).motivo_rechazo" class="mt-2 text-sm text-danger"><b>{{ t('verif.reason') }}:</b> {{ doc(tipo).motivo_rechazo }}</p>
              </div>
              <p v-else class="mt-3 text-sm text-muted">{{ t('verif.missing') }}</p>

              <form v-if="puedeSubir(tipo)" class="mt-4 space-y-3" @submit.prevent="subir(tipo)">
                <label class="block"><span class="campo-etiqueta">{{ doc(tipo) ? t('verif.replace') : t('verif.choose') }}</span>
                  <input type="file" accept="application/pdf,image/jpeg,image/png" class="campo-input file:mr-3 file:rounded-full file:border-0 file:bg-cream file:px-3 file:py-1 file:text-sm" :aria-invalid="!!formularios[tipo].campos.archivo" @change="elegir(tipo, $event)" />
                  <span class="mt-1 block text-xs text-muted">{{ t('verif.fileRules', { mb: maxMb }) }}</span>
                  <span v-if="formularios[tipo].campos.archivo" class="campo-error">{{ formularios[tipo].campos.archivo }}</span>
                </label>
                <label v-if="tipo === 'RUT'" class="block"><span class="campo-etiqueta">{{ t('verif.businessName') }}</span>
                  <input v-model="formularios.RUT.razonSocial" class="campo-input" maxlength="200" autocomplete="organization" :aria-invalid="!!formularios.RUT.campos.razon_social" />
                  <span v-if="formularios.RUT.campos.razon_social" class="campo-error">{{ formularios.RUT.campos.razon_social }}</span>
                </label>
                <p v-if="formularios[tipo].error" class="campo-error" role="alert">{{ formularios[tipo].error }}</p>
                <p v-if="formularios[tipo].ok" class="text-sm text-ok" role="status">{{ t('verif.sent') }}</p>
                <button type="submit" class="btn-primario" :disabled="!formularios[tipo].archivo || formularios[tipo].enviando || !enLinea">{{ formularios[tipo].enviando ? t('gestion.sending') : t('verif.upload') }}</button>
              </form>
              <p v-else class="mt-3 text-xs text-ok">{{ t('verif.approvedNote') }}</p>
            </article>
          </div>
        </template>
      </EstadoCarga>
    </div>
  </section>
</template>
