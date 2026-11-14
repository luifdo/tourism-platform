<script setup>
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { reviewUseCases } from '../../composition'
import { ASPECTOS, MAX_COMENTARIO } from '../../domain/gestion/resenas'
import { nuevaClave } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import EstrellasInput from './EstrellasInput.vue'

/*
 * UC15 · Escribir o editar mi reseña de un servicio que ya disfruté. Una por turista y servicio: la puntuación general es
 * obligatoria; los aspectos y el comentario, no. El envío lleva Idempotency-Key (una por intento): un reintento no duplica.
 */
const props = defineProps({ servicioId: { type: String, required: true }, resena: { type: Object, default: null } })
const emit = defineEmits(['guardada', 'cancelar'])
const { t } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const editando = !!props.resena
const f = reactive({ puntuacion: props.resena?.puntuacion ?? 0, aspectos: { ...(props.resena?.aspectos ?? {}) }, comentario: props.resena?.comentario ?? '' })
const enviando = ref(false)
const error = ref('')
const campos = ref({})
let ultimo = { huella: '', clave: '' }

async function enviar() {
  enviando.value = true; error.value = ''; campos.value = {}
  const huella = JSON.stringify(f)
  if (huella !== ultimo.huella) ultimo = { huella, clave: nuevaClave() }
  try {
    const r = editando
      ? await reviewUseCases.editar(props.resena.id, f, props.resena.version)
      : await reviewUseCases.escribir(props.servicioId, f, ultimo.clave)
    emit('guardada', r)
  } catch (e) {
    if (sesionVencida(e)) return
    campos.value = camposDe(e)
    error.value = e.code === 'VALIDACION' && e.campos?.length && !e.status ? t('resenas.fixErrors') : mensaje(e, 'resenas')
  } finally { enviando.value = false }
}
</script>

<template>
  <form class="tarjeta space-y-4" @submit.prevent="enviar">
    <h3 class="text-lg font-bold text-navy-darkest">{{ editando ? t('resenas.editTitle') : t('resenas.writeTitle') }}</h3>
    <div>
      <EstrellasInput v-model="f.puntuacion" :etiqueta="`${t('resenas.overall')} *`" nombre="puntuacion" />
      <p v-if="campos.puntuacion" class="campo-error" role="alert">{{ campos.puntuacion }}</p>
    </div>
    <fieldset>
      <legend class="text-sm font-semibold text-ink-control">{{ t('resenas.aspects') }} <span class="font-normal text-muted">({{ t('gestion.optional') }})</span></legend>
      <div class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <EstrellasInput v-for="a in ASPECTOS" :key="a" :model-value="f.aspectos[a] ?? 0" :etiqueta="t(`resenas.aspect.${a}`)" :nombre="`aspecto-${a}`" opcional @update:model-value="(v) => { v ? (f.aspectos[a] = v) : delete f.aspectos[a] }" />
      </div>
    </fieldset>
    <label class="block"><span class="campo-etiqueta">{{ t('resenas.comment') }}</span>
      <textarea v-model="f.comentario" rows="4" :maxlength="MAX_COMENTARIO" class="campo-input" :placeholder="t('resenas.commentPh')" />
      <span class="mt-1 block text-right font-mono text-[11px] text-muted">{{ f.comentario.length }}/{{ MAX_COMENTARIO }}</span>
    </label>
    <p class="text-xs text-muted">{{ t('resenas.publicNote') }}</p>
    <p v-if="error" class="campo-error" role="alert">{{ error }}</p>
    <div class="flex flex-wrap gap-3">
      <button type="submit" class="btn-primario" :disabled="enviando || !enLinea || !f.puntuacion">{{ enviando ? t('gestion.sending') : editando ? t('gestion.save') : t('resenas.publish') }}</button>
      <button type="button" class="btn-secundario" @click="emit('cancelar')">{{ t('gestion.cancel') }}</button>
    </div>
    <p v-if="!enLinea" class="text-xs text-muted">{{ t('gestion.needOnline') }}</p>
  </form>
</template>
