import { useState, useEffect } from 'react'
import './ProgressBar.css'

export default function ProgressBar({ status, photoCount }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(prev => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className="progress-container card">
      <div className="progress-spinner">
        <div className="spinner"></div>
      </div>
      <h2>Analyzing Shelf Photos</h2>
      <p className="progress-status">{status}</p>
      <p className="progress-detail">
        Processing {photoCount} photo{photoCount !== 1 ? 's' : ''} with Gemini AI...
      </p>
      <p className="progress-time">Elapsed: {formatTime(elapsed)}</p>
      <p className="progress-note">
        This typically takes 30-90 seconds depending on the number of photos and SKUs.
      </p>
    </div>
  )
}
