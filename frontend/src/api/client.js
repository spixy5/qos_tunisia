import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({ baseURL: API_BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('qos_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // No login screen anymore - clear the stale token and reload so
      // AuthProvider's effect silently re-authenticates in the background.
      localStorage.removeItem('qos_token')
      localStorage.removeItem('qos_role')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

// --- Auth ---
export const login = (username, password) =>
  api.post('/auth/login', { username, password }).then((r) => r.data)

// --- Dashboard (User session) ---
export const getGouvernorats = () => api.get('/dashboard/gouvernorats').then((r) => r.data)
export const getDelegations = (gouvernoratId) =>
  api.get('/dashboard/delegations', { params: { gouvernorat_id: gouvernoratId } }).then((r) => r.data)
export const getSecteurs = (delegationId) =>
  api.get('/dashboard/secteurs', { params: { delegation_id: delegationId } }).then((r) => r.data)
export const getBoundary = (level, id) =>
  api.get('/dashboard/boundary', { params: { level, id } }).then((r) => r.data)
export const getLocationOverview = (secteurId) =>
  api.get('/dashboard/location-overview', { params: { secteur_id: secteurId } }).then((r) => r.data)
export const getDelegationOverview = (delegationId) =>
  api.get('/dashboard/delegation-overview', { params: { delegation_id: delegationId } }).then((r) => r.data)
export const getMapPoints = (kpiName = 'PCPS') =>
  api.get('/dashboard/map-points', { params: { kpi_name: kpiName } }).then((r) => r.data)
export const getAreaQuality = ({ level, id, operator }) =>
  api.get('/dashboard/area-quality', { params: { level, id, operator } }).then((r) => r.data)
export const getRawLogs = ({ level, id, operator, result, logType, limit }) =>
  api.get('/dashboard/raw-logs', { params: { level, id, operator, result, log_type: logType, limit } }).then((r) => r.data)
export const getRsrpTrend = ({ level, id, operator, bucket }) =>
  api.get('/dashboard/rsrp-trend', { params: { level, id, operator, bucket } }).then((r) => r.data)
export const getBadRsrpPoints = ({ level, id, operator, technology }) =>
  api.get('/dashboard/bad-rsrp-points', { params: { level, id, operator, technology } }).then((r) => r.data)

// --- Admin: locations that actually have data (drives admin dropdowns) ---
export const getDataGouvernorats = () => api.get('/admin/locations/gouvernorats').then((r) => r.data)
export const getDataDelegations = (gouvernoratId) =>
  api.get('/admin/locations/delegations', { params: { gouvernorat_id: gouvernoratId } }).then((r) => r.data)
export const getDataSecteurs = (delegationId) =>
  api.get('/admin/locations/secteurs', { params: { delegation_id: delegationId } }).then((r) => r.data)
export const getUploadedFiles = () => api.get('/admin/files').then((r) => r.data)
export const recomputeKpis = () => api.post('/admin/recompute-kpis').then((r) => r.data)

// --- Admin session ---
export const getBandThresholds = () => api.get('/admin/thresholds/bands').then((r) => r.data)
export const upsertBandThreshold = (payload) => api.put('/admin/thresholds/bands', payload).then((r) => r.data)
export const getTechnologyThresholds = () => api.get('/admin/thresholds/technologies').then((r) => r.data)
export const upsertTechnologyThreshold = (payload) => api.put('/admin/thresholds/technologies', payload).then((r) => r.data)
export const getDurationThreshold = () => api.get('/admin/thresholds/duration').then((r) => r.data)
export const upsertDurationThreshold = (payload) => api.put('/admin/thresholds/duration', payload).then((r) => r.data)
export const getChannelBands = () => api.get('/admin/channel-bands').then((r) => r.data)
export const uploadFile = (formData, onProgress) =>
  api
    .post('/admin/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
    .then((r) => r.data)
export const deleteByFilePath = (archivePath) =>
  api.delete('/admin/data/by-file-path', { data: { archive_path: archivePath } }).then((r) => r.data)
export const deleteBySite = (secteurId) =>
  api.delete('/admin/data/by-site', { data: { secteur_id: secteurId } }).then((r) => r.data)
