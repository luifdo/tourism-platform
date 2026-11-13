import { onBeforeUnmount, onMounted, ref } from 'vue'

/** ¿Hay conexión? Reactivo. Confirmar, rechazar y editar el calendario necesitan red (SRS §3.6.6). */
export function useOnline() {
  const enLinea = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  const cambiar = () => { enLinea.value = navigator.onLine }
  onMounted(() => { window.addEventListener('online', cambiar); window.addEventListener('offline', cambiar) })
  onBeforeUnmount(() => { window.removeEventListener('online', cambiar); window.removeEventListener('offline', cambiar) })
  return enLinea
}
