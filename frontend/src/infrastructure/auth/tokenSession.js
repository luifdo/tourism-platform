/** Adaptador del puerto Session: el JWT que emite iam-service vive en localStorage (UC2). */
export const getToken = () => {
  try { return localStorage.getItem('token') } catch { return null }
}

export const tokenSession = Object.freeze({
  isAuthenticated: () => !!getToken(),
})
