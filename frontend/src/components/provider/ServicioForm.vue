<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { offerUseCases } from '../../composition'
import { CAMPOS, MEDIOS_PAGO, RECOMENDACIONES_DINERO, SENALES, TIPOS, UNIDADES_TARIFA, bloqueDeTipo, formularioDeServicio, formularioVacio, validarServicio } from '../../domain/gestion/servicio'
import { MAX_IMAGENES, nuevaClave } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import CampoAtributo from './CampoAtributo.vue'

/*
 * UC17 registrar / UC18 editar una oferta. Todo el armado y la validación viven en domain/gestion/servicio.js; aquí solo se
 * pinta el formulario, se piden las coordenadas (geocodificar), se suben las fotos y se llama al caso de uso.
 * La clave de idempotencia es una por intento: si el envío se corta y se repite sin cambiar nada, lleva la misma.
 */
const props = defineProps({ servicio: { type: Object, default: null }, zonas: { type: Array, default: () => [] } })
const emit = defineEmits(['guardado', 'cancelar'])
const { t, locale } = useI18n()
const { mensaje, sesionVencida } = useGestion()
const enLinea = useOnline()

const editando = !!props.servicio
const form = reactive(editando ? formularioDeServicio(props.servicio) : formularioVacio())
const errores = ref({})
const errorGeneral = ref('')
const enviando = ref(false)
const bloque = computed(() => bloqueDeTipo(form.tipo))
const categorias = [...new Set(Object.values(TIPOS).map((x) => x.categoria))]
const tiposDe = (cat) => Object.entries(TIPOS).filter(([, x]) => x.categoria === cat).map(([k]) => k)
const etiquetaCat = (c) => t(`explorer.filters.${c}`)
const err = (k) => (errores.value[k] ? t(`gestion.fieldErrors.${errores.value[k]}`) : '')

// ---- Ubicación: sugerir coordenadas desde una dirección (Nominatim, vía el catálogo); el prestador las confirma
const direccion = ref('')
const sugerencias = ref([])
const buscandoDir = ref(false)
const errorDir = ref('')
async function geocodificar() {
  buscandoDir.value = true; errorDir.value = ''; sugerencias.value = []
  try { sugerencias.value = await offerUseCases.geocodificar(direccion.value); if (!sugerencias.value.length) errorDir.value = t('oferta.noResults') }
  catch (e) { if (!sesionVencida(e)) errorDir.value = e.campos?.length ? t('gestion.fieldErrors.DIRECCION_INVALIDA') : mensaje(e, 'oferta') }
  finally { buscandoDir.value = false }
}
const usarSugerencia = (s) => { form.ubicacion.lat = Number(s.lat.toFixed(6)); form.ubicacion.lon = Number(s.lon.toFixed(6)); sugerencias.value = [] }
const enlaceOsm = computed(() => (Number.isFinite(Number(form.ubicacion.lat)) && form.ubicacion.lat !== '' && form.ubicacion.lon !== '' ? `https://www.openstreetmap.org/?mlat=${form.ubicacion.lat}&mlon=${form.ubicacion.lon}#map=16/${form.ubicacion.lat}/${form.ubicacion.lon}` : ''))

// ---- Fotos
const subiendo = ref(0)
const errorFotos = ref('')
async function agregarFotos(e) {
  errorFotos.value = ''
  const archivos = [...(e.target.files ?? [])]
  e.target.value = ''
  for (const a of archivos) {
    if (form.imagenes_urls.length >= MAX_IMAGENES) { errorFotos.value = t('gestion.fieldErrors.DEMASIADAS_IMAGENES'); break }
    subiendo.value++
    try { form.imagenes_urls.push(await offerUseCases.subirImagen(a)) }
    catch (x) { if (sesionVencida(x)) return; errorFotos.value = x.campos?.length ? t(`gestion.fieldErrors.${x.campos[0].mensaje}`) : mensaje(x, 'oferta') }
    finally { subiendo.value-- }
  }
}
const quitarFoto = (i) => form.imagenes_urls.splice(i, 1)
const portada = (i) => form.imagenes_urls.unshift(...form.imagenes_urls.splice(i, 1))

// ---- Envío
let ultimo = { huella: '', clave: '' }
function claveDelIntento() {
  const huella = JSON.stringify(form)
  if (huella !== ultimo.huella) ultimo = { huella, clave: nuevaClave() }
  return ultimo.clave
}
async function guardar() {
  errorGeneral.value = ''
  errores.value = validarServicio(form)
  if (Object.keys(errores.value).length) {
    errorGeneral.value = t('oferta.fixErrors')
    document.getElementById('servicio-form')?.querySelector('[aria-invalid="true"]')?.focus()
    return
  }
  enviando.value = true
  try {
    const clave = claveDelIntento()
    const s = editando
      ? await offerUseCases.editarServicio(props.servicio.id, form, props.servicio.version, props.servicio.atributos, clave)
      : await offerUseCases.crearServicio(form, clave)
    emit('guardado', s)
  } catch (e) {
    if (sesionVencida(e)) return
    if (e.code === 'VALIDACION' && e.campos?.length && !e.status) errores.value = Object.fromEntries(e.campos.map((c) => [c.campo, c.mensaje])) // validación local
    errorGeneral.value = e.code === 'VERSION_DISTINTA' ? t('oferta.errors.VERSION_DISTINTA') : e.campos?.length && !e.status ? t('oferta.fixErrors') : mensaje(e, 'oferta')
  } finally { enviando.value = false }
}
void locale
</script>

<template>
  <form id="servicio-form" class="space-y-6" novalidate @submit.prevent="guardar">
    <fieldset class="tarjeta space-y-4">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t('oferta.basics') }}</legend>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="campo-etiqueta">{{ t('oferta.nameEs') }} *</span><input v-model="form.nombre.es" class="campo-input" maxlength="200" :aria-invalid="!!errores.nombre" /><span v-if="errores.nombre" class="campo-error">{{ err('nombre') }}</span></label>
        <label><span class="campo-etiqueta">{{ t('oferta.nameEn') }}</span><input v-model="form.nombre.en" class="campo-input" maxlength="200" /></label>
        <label><span class="campo-etiqueta">{{ t('oferta.descEs') }} *</span><textarea v-model="form.descripcion.es" rows="4" class="campo-input" :aria-invalid="!!errores.descripcion" /><span v-if="errores.descripcion" class="campo-error">{{ err('descripcion') }}</span></label>
        <label><span class="campo-etiqueta">{{ t('oferta.descEn') }}</span><textarea v-model="form.descripcion.en" rows="4" class="campo-input" /></label>
      </div>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label class="sm:col-span-2"><span class="campo-etiqueta">{{ t('oferta.type') }} *</span>
          <select v-model="form.tipo" class="campo-input" :aria-invalid="!!errores.tipo">
            <option value="">—</option>
            <optgroup v-for="c in categorias" :key="c" :label="etiquetaCat(c)"><option v-for="tp in tiposDe(c)" :key="tp" :value="tp">{{ t(`oferta.opts.${tp}`) }}</option></optgroup>
          </select>
          <span v-if="errores.tipo" class="campo-error">{{ err('tipo') }}</span>
        </label>
        <label><span class="campo-etiqueta">{{ t('oferta.rate') }} (COP) *</span><input v-model="form.tarifa_base" type="number" min="0" step="any" inputmode="decimal" class="campo-input" :aria-invalid="!!errores.tarifa_base" /><span v-if="errores.tarifa_base" class="campo-error">{{ err('tarifa_base') }}</span></label>
        <label><span class="campo-etiqueta">{{ t('oferta.unit') }} *</span><select v-model="form.unidad_tarifa" class="campo-input"><option v-for="u in UNIDADES_TARIFA" :key="u" :value="u">{{ t(`oferta.opts.${u}`) }}</option></select></label>
        <label><span class="campo-etiqueta">{{ t('oferta.capacity') }} *</span><input v-model="form.capacidad_aforo_diario" type="number" min="1" step="1" class="campo-input" :aria-invalid="!!errores.capacidad_aforo_diario" /><span v-if="errores.capacidad_aforo_diario" class="campo-error">{{ err('capacidad_aforo_diario') }}</span></label>
      </div>
    </fieldset>

    <fieldset class="tarjeta space-y-4">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t('oferta.location') }}</legend>
      <p class="text-sm text-muted">{{ t('oferta.locationHint') }}</p>
      <div class="flex flex-wrap items-end gap-3">
        <label class="min-w-[220px] flex-1"><span class="campo-etiqueta">{{ t('oferta.address') }}</span><input v-model="direccion" class="campo-input" maxlength="200" :placeholder="t('oferta.addressPh')" @keydown.enter.prevent="geocodificar" /></label>
        <button type="button" class="btn-secundario" :disabled="buscandoDir || !enLinea" @click="geocodificar">{{ buscandoDir ? t('gestion.searching') : t('oferta.findPoint') }}</button>
      </div>
      <p v-if="errorDir" class="campo-error" role="alert">{{ errorDir }}</p>
      <ul v-if="sugerencias.length" class="divide-y divide-sand/30 rounded-xl border border-sand/40 bg-cream">
        <li v-for="s in sugerencias" :key="`${s.lat},${s.lon}`"><button type="button" class="block w-full px-4 py-2 text-left text-sm text-ink-control hover:bg-white" @click="usarSugerencia(s)">{{ s.etiqueta }} <span class="font-mono text-xs text-muted">({{ s.lat.toFixed(4) }}, {{ s.lon.toFixed(4) }})</span></button></li>
      </ul>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="campo-etiqueta">{{ t('oferta.lat') }} *</span><input v-model="form.ubicacion.lat" type="number" step="any" min="-90" max="90" class="campo-input" :aria-invalid="!!errores.ubicacion" /></label>
        <label><span class="campo-etiqueta">{{ t('oferta.lon') }} *</span><input v-model="form.ubicacion.lon" type="number" step="any" min="-180" max="180" class="campo-input" :aria-invalid="!!errores.ubicacion" /></label>
      </div>
      <p v-if="errores.ubicacion" class="campo-error">{{ err('ubicacion') }}</p>
      <a v-if="enlaceOsm" :href="enlaceOsm" target="_blank" rel="noopener noreferrer" class="inline-block text-sm font-medium text-navy underline hover:text-teal">{{ t('oferta.checkOnMap') }}</a>
    </fieldset>

    <fieldset class="tarjeta">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t('oferta.photos') }}</legend>
      <p class="mt-1 text-sm text-muted">{{ t('oferta.photosHint', { n: MAX_IMAGENES }) }}</p>
      <ul v-if="form.imagenes_urls.length" class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <li v-for="(u, i) in form.imagenes_urls" :key="u" class="relative overflow-hidden rounded-xl border border-sand/40 bg-cream">
          <img :src="u" alt="" class="aspect-[4/3] w-full object-cover" loading="lazy" />
          <span v-if="i === 0" class="pildora absolute left-1.5 top-1.5 bg-navy-darkest/85 text-white">{{ t('oferta.cover') }}</span>
          <div class="flex justify-between gap-1 p-1.5 text-xs">
            <button v-if="i > 0" type="button" class="font-medium text-navy underline" @click="portada(i)">{{ t('oferta.makeCover') }}</button><span v-else />
            <button type="button" class="font-medium text-danger underline" @click="quitarFoto(i)">{{ t('gestion.remove') }}</button>
          </div>
        </li>
      </ul>
      <label class="btn-secundario mt-3 cursor-pointer" :class="{ 'opacity-50': !enLinea || subiendo }">
        {{ subiendo ? t('gestion.sending') : t('oferta.addPhotos') }}
        <input type="file" accept="image/jpeg,image/png,image/webp" multiple class="sr-only" :disabled="!enLinea || form.imagenes_urls.length >= MAX_IMAGENES" @change="agregarFotos" />
      </label>
      <p v-if="errorFotos" class="campo-error" role="alert">{{ errorFotos }}</p>
    </fieldset>

    <fieldset class="tarjeta space-y-4">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t('oferta.essentials') }}</legend>
      <div class="grid gap-4 sm:grid-cols-2">
        <CampoAtributo
          v-for="[k, clase, req, ops] in CAMPOS.comunes" :id="`c-${k}`" :key="k" v-model="form.bloques.comunes[k]" :campo="k" :clase="clase" :obligatorio="!!req" :opciones="ops ?? []" :error="err(`comunes.${k}`)"
        />
      </div>
    </fieldset>

    <fieldset v-if="bloque" class="tarjeta space-y-4">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t(`attrs.sections.${bloque}`) }}</legend>
      <div class="grid gap-4 sm:grid-cols-2">
        <CampoAtributo
          v-for="[k, clase, req, ops] in CAMPOS[bloque]" :id="`b-${k}`" :key="`${bloque}-${k}`" v-model="form.bloques[bloque][k]" :campo="k" :clase="clase" :obligatorio="!!req" :opciones="ops ?? []" :error="err(`${bloque}.${k}`)"
        />
      </div>
    </fieldset>
    <p v-else class="text-sm text-muted">{{ t('oferta.pickTypeHint') }}</p>

    <fieldset class="tarjeta space-y-4">
      <legend class="px-1 text-lg font-bold text-navy-darkest">{{ t('attrs.sections.pagos') }}</legend>
      <p class="text-sm text-muted">{{ t('oferta.paymentsHint') }}</p>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="campo-etiqueta">{{ t('attrs.fields.senal_internet') }}</span>
          <select v-model="form.pagos.senal_internet" class="campo-input" :aria-invalid="!!errores.pagos"><option value="">—</option><option v-for="s in SENALES" :key="s" :value="s">{{ t(`oferta.opts.${s}`) }}</option></select>
        </label>
        <label><span class="campo-etiqueta">{{ t('oferta.moneyAdvice') }}</span>
          <select v-model="form.pagos.recomendacion_dinero" class="campo-input" :aria-invalid="!!errores.pagos"><option value="">—</option><option v-for="s in RECOMENDACIONES_DINERO" :key="s" :value="s">{{ t(`oferta.opts.REC_${s}`) }}</option></select>
        </label>
        <fieldset class="sm:col-span-2"><legend class="campo-etiqueta">{{ t('attrs.fields.medios_pago') }}</legend>
          <div class="mt-1 flex flex-wrap gap-2">
            <label v-for="m in MEDIOS_PAGO" :key="m" class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-sand/40 bg-white px-3 py-1 text-sm text-ink-control transition has-[:checked]:border-navy has-[:checked]:bg-navy has-[:checked]:text-white">
              <input v-model="form.pagos.medios_pago" type="checkbox" class="sr-only" :value="m" />{{ t(`oferta.opts.${m}`) }}
            </label>
          </div>
        </fieldset>
      </div>
      <p v-if="errores.pagos" class="campo-error" role="alert">{{ err('pagos') }}</p>
    </fieldset>

    <div v-if="errorGeneral" class="rounded-card border border-danger/30 bg-danger-bg p-4 text-sm text-danger" role="alert">{{ errorGeneral }}</div>
    <div class="flex flex-wrap items-center gap-3">
      <button type="submit" class="btn-primario" :disabled="enviando || subiendo > 0 || !enLinea">{{ enviando ? t('gestion.saving') : editando ? t('oferta.saveChanges') : t('oferta.publish') }}</button>
      <button type="button" class="btn-secundario" @click="emit('cancelar')">{{ t('gestion.cancel') }}</button>
      <span v-if="!enLinea" class="text-xs text-muted">{{ t('gestion.needOnline') }}</span>
    </div>
  </form>
</template>
