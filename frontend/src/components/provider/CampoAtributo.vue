<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { TIPOS_HABITACION, TIPOS_VISITANTE } from '../../domain/gestion/servicio'

/*
 * Un campo de los atributos de una oferta, pintado según su clase (ver CAMPOS en domain/gestion/servicio.js).
 * Es un v-model: recibe el valor del campo y avisa el valor nuevo; el formulario es quien lo guarda.
 */
const props = defineProps({
  campo: { type: String, required: true }, clase: { type: String, required: true }, obligatorio: Boolean,
  opciones: { type: Array, default: () => [] }, modelValue: { type: null, default: undefined }, error: { type: String, default: '' }, id: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const set = (v) => emit('update:modelValue', v)
const etiqueta = computed(() => t(`attrs.fields.${props.campo}`) + (props.obligatorio ? ' *' : ''))
const opt = (c) => t(`oferta.opts.${c}`)

// Sí / No / sin informar: un tercer estado, porque "no informado" no es lo mismo que "no"
const triestado = computed({ get: () => (props.modelValue === true ? 'si' : props.modelValue === false ? 'no' : ''), set: (v) => set(v === 'si' ? true : v === 'no' ? false : null) })

const alternar = (c) => { const l = new Set(props.modelValue ?? []); l.has(c) ? l.delete(c) : l.add(c); set([...l]) }
const cambiarFila = (lista, i, cambio) => set(lista.map((x, j) => (j === i ? { ...x, ...cambio } : x)))
const quitarFila = (lista, i) => set(lista.filter((_, j) => j !== i))
const textoEn = (e) => set({ ...props.modelValue, en: e.target.value })
const textoEs = (e) => set({ ...props.modelValue, es: e.target.value })
</script>

<template>
  <div :class="['txt', 'habitaciones', 'tarifas', 'multi'].includes(clase) ? 'sm:col-span-2' : ''">
    <!-- Texto en español e inglés -->
    <template v-if="clase === 'txt'">
      <span :id="`${id}-l`" class="campo-etiqueta">{{ etiqueta }}</span>
      <div class="mt-1 grid gap-2 sm:grid-cols-2">
        <textarea :id="id" :value="modelValue?.es" rows="2" class="campo-input !mt-0" :placeholder="t('oferta.inEs')" :aria-labelledby="`${id}-l`" :aria-invalid="!!error" @input="textoEs" />
        <textarea :value="modelValue?.en" rows="2" class="campo-input !mt-0" :placeholder="t('oferta.inEn')" :aria-labelledby="`${id}-l`" @input="textoEn" />
      </div>
    </template>

    <label v-else-if="clase === 'int' || clase === 'num'" :for="id">
      <span class="campo-etiqueta">{{ etiqueta }}</span>
      <input :id="id" type="number" :min="0" :step="clase === 'int' ? 1 : 'any'" inputmode="decimal" class="campo-input" :value="modelValue" :aria-invalid="!!error" @input="set($event.target.value)" />
    </label>

    <label v-else-if="clase === 'hora'" :for="id">
      <span class="campo-etiqueta">{{ etiqueta }}</span>
      <input :id="id" type="time" class="campo-input" :value="modelValue" :aria-invalid="!!error" @input="set($event.target.value)" />
    </label>

    <label v-else-if="clase === 'horas'" :for="id">
      <span class="campo-etiqueta">{{ etiqueta }}</span>
      <input :id="id" class="campo-input" :value="modelValue" placeholder="08:00, 14:30" :aria-invalid="!!error" @input="set($event.target.value)" />
      <span class="mt-1 block text-xs text-muted">{{ t('oferta.hoursHint') }}</span>
    </label>

    <label v-else-if="clase === 'sel'" :for="id">
      <span class="campo-etiqueta">{{ etiqueta }}</span>
      <select :id="id" class="campo-input" :value="modelValue" :aria-invalid="!!error" @change="set($event.target.value)">
        <option value="">—</option>
        <option v-for="o in opciones" :key="o" :value="o">{{ opt(o) }}</option>
      </select>
    </label>

    <label v-else-if="clase === 'bool'" :for="id">
      <span class="campo-etiqueta">{{ etiqueta }}</span>
      <select :id="id" v-model="triestado" class="campo-input">
        <option value="">{{ t('oferta.notSaid') }}</option>
        <option value="si">{{ t('attrs.yes') }}</option>
        <option value="no">{{ t('attrs.no') }}</option>
      </select>
    </label>

    <fieldset v-else-if="clase === 'multi'">
      <legend class="campo-etiqueta">{{ etiqueta }}</legend>
      <div class="mt-1 flex flex-wrap gap-2">
        <label v-for="o in opciones" :key="o" class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition has-[:checked]:border-navy has-[:checked]:bg-navy has-[:checked]:text-white" :class="'border-sand/40 bg-white text-ink-control'">
          <input type="checkbox" class="sr-only" :checked="(modelValue ?? []).includes(o)" @change="alternar(o)" />{{ opt(o) }}
        </label>
      </div>
    </fieldset>

    <fieldset v-else-if="clase === 'habitaciones'">
      <legend class="campo-etiqueta">{{ etiqueta }}</legend>
      <ul class="mt-1 space-y-2">
        <li v-for="(h, i) in modelValue ?? []" :key="i" class="grid grid-cols-[1fr_88px_88px_auto] items-end gap-2">
          <label><span class="sr-only">{{ t('oferta.roomType') }}</span>
            <select class="campo-input !mt-0" :value="h.tipo" @change="cambiarFila(modelValue, i, { tipo: $event.target.value })"><option value="">{{ t('oferta.roomType') }}</option><option v-for="o in TIPOS_HABITACION" :key="o" :value="o">{{ opt(o) }}</option></select>
          </label>
          <label><span class="sr-only">{{ t('oferta.roomPeople') }}</span><input type="number" min="1" max="50" class="campo-input !mt-0" :placeholder="t('oferta.roomPeople')" :value="h.capacidad_personas" @input="cambiarFila(modelValue, i, { capacidad_personas: $event.target.value })" /></label>
          <label><span class="sr-only">{{ t('oferta.roomCount') }}</span><input type="number" min="1" max="500" class="campo-input !mt-0" :placeholder="t('oferta.roomCount')" :value="h.cantidad" @input="cambiarFila(modelValue, i, { cantidad: $event.target.value })" /></label>
          <button type="button" class="px-2 py-2 text-sm text-danger" :aria-label="t('gestion.remove')" @click="quitarFila(modelValue, i)">✕</button>
        </li>
      </ul>
      <button type="button" class="btn-secundario mt-2 !py-1.5" @click="set([...(modelValue ?? []), { tipo: '', capacidad_personas: '', cantidad: 1 }])">+ {{ t('oferta.addRoom') }}</button>
    </fieldset>

    <fieldset v-else-if="clase === 'tarifas'">
      <legend class="campo-etiqueta">{{ etiqueta }}</legend>
      <ul class="mt-1 space-y-2">
        <li v-for="(x, i) in modelValue ?? []" :key="i" class="grid grid-cols-[1fr_140px_auto] items-end gap-2">
          <label><span class="sr-only">{{ t('oferta.visitorType') }}</span>
            <select class="campo-input !mt-0" :value="x.tipo_visitante" @change="cambiarFila(modelValue, i, { tipo_visitante: $event.target.value })"><option value="">{{ t('oferta.visitorType') }}</option><option v-for="o in TIPOS_VISITANTE" :key="o" :value="o">{{ opt(o) }}</option></select>
          </label>
          <label><span class="sr-only">{{ t('oferta.rate') }}</span><input type="number" min="0" class="campo-input !mt-0" :placeholder="t('oferta.rate')" :value="x.valor" @input="cambiarFila(modelValue, i, { valor: $event.target.value })" /></label>
          <button type="button" class="px-2 py-2 text-sm text-danger" :aria-label="t('gestion.remove')" @click="quitarFila(modelValue, i)">✕</button>
        </li>
      </ul>
      <button type="button" class="btn-secundario mt-2 !py-1.5" @click="set([...(modelValue ?? []), { tipo_visitante: '', valor: '' }])">+ {{ t('oferta.addRate') }}</button>
    </fieldset>

    <p v-if="error" class="campo-error" role="alert">{{ error }}</p>
  </div>
</template>
