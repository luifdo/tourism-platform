<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import { useSession } from '../../ui/useSession'
import { fmtMomento } from '../../ui/format'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Paginacion from '../shared/Paginacion.vue'

/*
 * UC27 · Usuarios y roles: buscar, cambiar el rol y activar o desactivar cuentas. Cambiar el rol o desactivar revoca las
 * sesiones de la persona. No se puede modificar la propia cuenta ni dejar la plataforma sin administradores (lo valida el servicio).
 */
const emit = defineEmits(['ver-bitacora'])
const ROLES = ['Turista', 'Prestador', 'Entidad', 'Admin']
const { t, locale } = useI18n()
const { mensaje, sesionVencida } = useGestion()
const { sesion } = useSession()
const enLinea = useOnline()

const filtros = reactive({ q: '', rol: '', activo: '' })
const datos = ref({ items: [], pagina: 1, tamano: 15, total: 0 })
const cargando = ref(true)
const error = ref('')
const aviso = ref('')
const accion = reactive({ id: '', tipo: '', rol: 'Turista', activo: true, motivo: '', enviando: false, error: '' })

async function cargar(pagina = 1) {
  cargando.value = true; error.value = ''
  try { datos.value = await adminUseCases.usuarios({ pagina, tamano: 15, q: filtros.q, rol: filtros.rol || undefined, activo: filtros.activo === '' ? undefined : filtros.activo === 'true' }) }
  catch (e) { if (!sesionVencida(e)) error.value = mensaje(e, 'admin') } finally { cargando.value = false }
}
onMounted(() => cargar())
watch(() => [filtros.rol, filtros.activo], () => cargar())

const esYo = (u) => u.id === sesion.usuario?.id
const abrir = (u, tipo) => Object.assign(accion, { id: u.id, tipo, rol: u.rol, activo: !u.activo, motivo: '', error: '' })
async function confirmar(u) {
  accion.enviando = true; accion.error = ''
  try {
    if (accion.tipo === 'rol') await adminUseCases.cambiarRol(u.id, { rol: accion.rol, motivo: accion.motivo })
    else await adminUseCases.cambiarEstado(u.id, { activo: accion.activo, motivo: accion.motivo })
    aviso.value = t(accion.tipo === 'rol' ? 'admin.roleChanged' : accion.activo ? 'admin.activated' : 'admin.deactivated', { nombre: u.nombre_completo })
    accion.id = ''
    await cargar(datos.value.pagina)
  } catch (e) { if (!sesionVencida(e)) accion.error = mensaje(e, 'admin') } finally { accion.enviando = false }
}
</script>

<template>
  <section aria-labelledby="h-usu">
    <h2 id="h-usu" class="text-lg font-bold text-navy-darkest">{{ t('admin.usersTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('admin.usersLead') }}</p>

    <form class="mt-4 flex flex-wrap items-end gap-3" role="search" @submit.prevent="cargar()">
      <label class="min-w-[220px] flex-1"><span class="campo-etiqueta">{{ t('admin.search') }}</span><input v-model="filtros.q" type="search" maxlength="100" class="campo-input" :placeholder="t('admin.searchPh')" /></label>
      <label><span class="campo-etiqueta">{{ t('perfil.role') }}</span><select v-model="filtros.rol" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option v-for="r in ROLES" :key="r" :value="r">{{ t(`perfil.roles.${r}`) }}</option></select></label>
      <label><span class="campo-etiqueta">{{ t('admin.status') }}</span><select v-model="filtros.activo" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option value="true">{{ t('admin.activeOnly') }}</option><option value="false">{{ t('admin.inactiveOnly') }}</option></select></label>
      <button type="submit" class="btn-primario">{{ t('admin.searchGo') }}</button>
    </form>
    <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!datos.items.length" :texto-vacio="t('admin.usersEmpty')" alto="h-40" @reintentar="cargar(datos.pagina)">
        <ul class="space-y-3">
          <li v-for="u in datos.items" :key="u.id" class="tarjeta !p-4">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="flex flex-wrap items-center gap-2"><span class="font-semibold text-navy-darkest">{{ u.nombre_completo }}</span><span class="pildora bg-teal/15 text-teal">{{ t(`perfil.roles.${u.rol}`) }}</span><span v-if="!u.activo" class="pildora bg-danger-bg text-danger">{{ t('admin.inactive') }}</span><span v-if="esYo(u)" class="pildora bg-sand/20 text-ink-control">{{ t('admin.you') }}</span></p>
                <p class="mt-0.5 break-all font-mono text-xs text-muted">{{ u.email }} · {{ t('admin.since', { fecha: fmtMomento(u.creado_en, locale, false) }) }}</p>
              </div>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <button type="button" class="font-medium text-navy underline hover:text-teal" :title="u.id" @click="emit('ver-bitacora', u.id)">{{ t('admin.viewAudit') }}</button>
                <template v-if="!esYo(u) && accion.id !== u.id">
                  <button type="button" class="font-medium text-navy underline hover:text-teal" :disabled="!enLinea" @click="abrir(u, 'rol')">{{ t('admin.changeRole') }}</button>
                  <button type="button" class="font-medium underline" :class="u.activo ? 'text-danger' : 'text-ok'" :disabled="!enLinea" @click="abrir(u, 'estado')">{{ u.activo ? t('admin.deactivate') : t('admin.activate') }}</button>
                </template>
              </div>
            </div>
            <form v-if="accion.id === u.id" class="mt-3 space-y-3 rounded-xl border border-sand/40 p-3" @submit.prevent="confirmar(u)">
              <label v-if="accion.tipo === 'rol'" class="block"><span class="campo-etiqueta">{{ t('admin.newRole') }}</span><select v-model="accion.rol" class="campo-input"><option v-for="r in ROLES" :key="r" :value="r">{{ t(`perfil.roles.${r}`) }}</option></select></label>
              <p v-else class="text-sm text-ink-control">{{ accion.activo ? t('admin.activateConfirm') : t('admin.deactivateConfirm') }}</p>
              <p class="text-xs text-muted">{{ t('admin.revokesSessions') }}</p>
              <label class="block"><span class="campo-etiqueta">{{ t('admin.reasonOptional') }}</span><textarea v-model="accion.motivo" rows="2" maxlength="2000" class="campo-input" /></label>
              <p v-if="accion.error" class="campo-error" role="alert">{{ accion.error }}</p>
              <div class="flex gap-3"><button type="submit" class="btn-primario" :disabled="accion.enviando || (accion.tipo === 'rol' && accion.rol === u.rol)">{{ accion.enviando ? t('gestion.sending') : t('gestion.confirm') }}</button><button type="button" class="btn-secundario" @click="accion.id = ''">{{ t('gestion.cancel') }}</button></div>
            </form>
          </li>
        </ul>
        <Paginacion :pagina="datos.pagina" :tamano="datos.tamano" :total="datos.total" @cambiar="cargar" />
      </EstadoCarga>
    </div>
  </section>
</template>
