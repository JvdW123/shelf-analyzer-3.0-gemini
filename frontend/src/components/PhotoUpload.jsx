import { useCallback, useState, useRef } from 'react'
import './PhotoUpload.css'

export default function PhotoUpload({ onPhotosSelected }) {
  const [dragOver, setDragOver] = useState(false)
  const [previews, setPreviews] = useState([])
  const [files, setFiles] = useState([])
  const inputRef = useRef(null)

  const processFiles = useCallback((newFiles) => {
    const imageFiles = Array.from(newFiles).filter(f =>
      f.type.startsWith('image/')
    )
    if (imageFiles.length === 0) return

    setFiles(prev => {
      const combined = [...prev, ...imageFiles]
      return combined
    })

    // Generate previews
    for (const file of imageFiles) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreviews(prev => [...prev, {
          name: file.name,
          url: e.target.result,
          size: (file.size / 1024 / 1024).toFixed(1),
        }])
      }
      reader.readAsDataURL(file)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    processFiles(e.dataTransfer.files)
  }, [processFiles])

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => setDragOver(false)

  const handleFileInput = (e) => {
    processFiles(e.target.files)
  }

  const removePhoto = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
    setPreviews(prev => prev.filter((_, i) => i !== index))
  }

  const handleContinue = () => {
    if (files.length > 0) {
      onPhotosSelected(files)
    }
  }

  return (
    <div className="photo-upload card">
      <h2>Upload Shelf Photos</h2>
      <p className="description">
        Upload overview and close-up photos of the shelf. Include at least one overview shot
        showing the full shelf layout, plus close-ups for label details.
      </p>

      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <div className="drop-icon">+</div>
        <p className="drop-text">Drag & drop photos here</p>
        <p className="drop-subtext">or click to browse</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileInput}
          style={{ display: 'none' }}
        />
      </div>

      {previews.length > 0 && (
        <>
          <div className="photo-count">
            {previews.length} photo{previews.length !== 1 ? 's' : ''} selected
          </div>
          <div className="preview-grid">
            {previews.map((preview, index) => (
              <div key={index} className="preview-item">
                <img src={preview.url} alt={preview.name} />
                <div className="preview-info">
                  <span className="preview-name" title={preview.name}>{preview.name}</span>
                  <span className="preview-size">{preview.size} MB</span>
                </div>
                <button
                  className="preview-remove"
                  onClick={(e) => { e.stopPropagation(); removePhoto(index) }}
                  title="Remove"
                >
                  x
                </button>
              </div>
            ))}
          </div>

          <div className="upload-actions">
            <button className="btn btn-primary" onClick={handleContinue}>
              Continue with {previews.length} photo{previews.length !== 1 ? 's' : ''}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
