import { useState } from 'react'
import PhotoUpload from './components/PhotoUpload'
import MetadataForm from './components/MetadataForm'
import ResultsView from './components/ResultsView'
import ProgressBar from './components/ProgressBar'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

const STEPS = {
  UPLOAD: 0,
  METADATA: 1,
  PROCESSING: 2,
  RESULTS: 3,
}

function App() {
  const [step, setStep] = useState(STEPS.UPLOAD)
  const [photos, setPhotos] = useState([])
  const [metadata, setMetadata] = useState({
    country: '',
    city: '',
    retailer: '',
    store_format: '',
    store_name: '',
    shelf_location: '',
  })
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [processingStatus, setProcessingStatus] = useState('')

  const handlePhotosSelected = async (files) => {
    setPhotos(files)
    setError(null)

    // Parse metadata from file names
    const filenames = files.map(f => f.name)
    try {
      const res = await fetch(`${API_BASE}/api/parse-metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(filenames),
      })
      if (res.ok) {
        const parsed = await res.json()
        setMetadata(prev => {
          const updated = { ...prev }
          for (const [key, value] of Object.entries(parsed)) {
            if (value && key !== 'currency') {
              updated[key] = value
            }
          }
          return updated
        })
      }
    } catch {
      // Metadata parsing is optional, continue silently
    }

    setStep(STEPS.METADATA)
  }

  const handleAnalyze = async (finalMetadata) => {
    setMetadata(finalMetadata)
    setStep(STEPS.PROCESSING)
    setProcessingStatus('Uploading photos and analyzing shelf...')
    setError(null)

    const formData = new FormData()
    for (const photo of photos) {
      formData.append('photos', photo)
    }
    formData.append('metadata', JSON.stringify(finalMetadata))

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Analysis failed')
      }

      const data = await res.json()
      setResults(data)
      setStep(STEPS.RESULTS)
    } catch (err) {
      setError(err.message)
      setStep(STEPS.METADATA)
    }
  }

  const handleDownloadExcel = async () => {
    if (!results) return

    try {
      const res = await fetch(`${API_BASE}/api/generate-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skus: results.skus,
          session_id: results.session_id,
        }),
      })

      if (!res.ok) throw new Error('Excel generation failed')

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `shelf_analysis_${results.session_id}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleReset = () => {
    setStep(STEPS.UPLOAD)
    setPhotos([])
    setMetadata({
      country: '',
      city: '',
      retailer: '',
      store_format: '',
      store_name: '',
      shelf_location: '',
    })
    setResults(null)
    setError(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Shelf Analyzer 3.0</h1>
        <p className="subtitle">Upload shelf photos, get structured SKU data</p>
      </header>

      <div className="step-indicator">
        {['Upload Photos', 'Store Details', 'Analyzing', 'Results'].map((label, i) => (
          <div key={i} className={`step ${step === i ? 'active' : ''} ${step > i ? 'done' : ''}`}>
            <span className="step-number">{step > i ? '\u2713' : i + 1}</span>
            <span className="step-label">{label}</span>
          </div>
        ))}
      </div>

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {step === STEPS.UPLOAD && (
          <PhotoUpload onPhotosSelected={handlePhotosSelected} />
        )}

        {step === STEPS.METADATA && (
          <MetadataForm
            metadata={metadata}
            photoCount={photos.length}
            onAnalyze={handleAnalyze}
            onBack={() => setStep(STEPS.UPLOAD)}
          />
        )}

        {step === STEPS.PROCESSING && (
          <ProgressBar status={processingStatus} photoCount={photos.length} />
        )}

        {step === STEPS.RESULTS && results && (
          <ResultsView
            results={results}
            onDownloadExcel={handleDownloadExcel}
            onNewAnalysis={handleReset}
          />
        )}
      </main>
    </div>
  )
}

export default App
