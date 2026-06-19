import { ref } from 'vue'
import axios from 'axios'
import Papa from 'papaparse'

const api = axios.create({
  baseURL: '/api'
})

export function useDataLoader() {
  const loading = ref(false)
  const error = ref(null)

  const fetchCsv = async (layer, filename) => {
    loading.value = true
    error.value = null
    try {
      const timestamp = Date.now()
      const res = await api.get(`/data/${layer}/${filename}?_t=${timestamp}`)
      return new Promise((resolve, reject) => {
        Papa.parse(res.data, {
          header: true,
          dynamicTyping: true,
          skipEmptyLines: true,
          complete: (results) => resolve(results.data),
          error: (err) => reject(err)
        })
      })
    } catch (err) {
      if (err.response && err.response.status === 404) {
        // Silently ignore missing files, they just mean no data
      } else {
        error.value = err.message
        console.error(err)
      }
      return []
    } finally {
      loading.value = false
    }
  }

  const fetchJson = async (layer, filename) => {
    loading.value = true
    error.value = null
    try {
      const timestamp = Date.now()
      const res = await api.get(`/data/${layer}/${filename}?_t=${timestamp}`)
      return res.data
    } catch (err) {
      if (err.response && err.response.status === 404) {
        // Silently ignore missing files
      } else {
        error.value = err.message
        console.error(err)
      }
      return null
    } finally {
      loading.value = false
    }
  }
  
  const fetchTopics = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await api.get('/data/topics')
      return res.data
    } catch (err) {
      error.value = err.message
      console.error(err)
      return { topics: [], klines: {} }
    } finally {
      loading.value = false
    }
  }

  const fetchReports = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await api.get('/data/reports')
      return res.data
    } catch (err) {
      error.value = err.message
      console.error(err)
      return []
    } finally {
      loading.value = false
    }
  }

  const triggerRealtimeFetch = async (symbol, layer = null) => {
    loading.value = true
    error.value = null
    try {
      const url = layer ? `/stock/${symbol}/fetch?layer=${layer}` : `/stock/${symbol}/fetch`
      const res = await api.get(url)
      return res.data
    } catch (err) {
      error.value = err.message
      console.error(err)
      return null
    } finally {
      loading.value = false
    }
  }

  const triggerBackendRefresh = async () => {
    try {
      const res = await api.post('/refresh')
      return res.data
    } catch (err) {
      console.error('Failed to trigger backend refresh:', err)
      return { status: 'error', message: err.message }
    }
  }

  const checkRefreshStatus = async () => {
    try {
      const res = await api.get('/refresh/status')
      return res.data
    } catch (err) {
      console.error('Failed to check refresh status:', err)
      return { running: false, last_result: 'error' }
    }
  }

  const triggerRiskAudit = async (symbol) => {
    loading.value = true
    try {
      const res = await api.post(`/stock/audit/${symbol}`)
      return res.data
    } catch (err) {
      console.error('Failed to trigger risk audit:', err)
      return { status: 'error', message: err.message }
    } finally {
      loading.value = false
    }
  }

  const fetchNlpSummaries = async (symbol) => {
    loading.value = true
    try {
      const res = await api.get(`/stock/${symbol}/nlp_summaries`)
      if (res.data && res.data.status === 'success') {
        return res.data.data
      }
      return null
    } catch (err) {
      console.error('Failed to fetch nlp summaries:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  const triggerReportsRefresh = async () => {
    try {
      const res = await api.post('/refresh/reports')
      return res.data
    } catch (err) {
      console.error('Failed to trigger reports refresh:', err)
      return { status: 'error', message: err.message }
    }
  }

  const checkReportsRefreshStatus = async () => {
    try {
      const res = await api.get('/refresh/reports/status')
      return res.data
    } catch (err) {
      console.error('Failed to check reports refresh status:', err)
      return { running: false, last_result: 'error' }
    }
  }

  const triggerTopicsRefresh = async () => {
    try {
      const res = await api.post('/refresh/topics')
      return res.data
    } catch (err) {
      console.error('Failed to trigger topics refresh:', err)
      return { status: 'error', message: err.message }
    }
  }

  const checkTopicsRefreshStatus = async () => {
    try {
      const res = await api.get('/refresh/topics/status')
      return res.data
    } catch (err) {
      console.error('Failed to check topics refresh status:', err)
      return { running: false, last_result: 'error' }
    }
  }

  return { loading, error, fetchCsv, fetchJson, fetchTopics, fetchReports, triggerRealtimeFetch, triggerBackendRefresh, checkRefreshStatus, triggerRiskAudit, triggerReportsRefresh, checkReportsRefreshStatus, triggerTopicsRefresh, checkTopicsRefreshStatus, fetchNlpSummaries }
}
