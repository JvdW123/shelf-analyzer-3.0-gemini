import { useState } from 'react'
import './MetadataForm.css'

const STORE_FORMATS = [
  'Supermarket',
  'Hypermarket',
  'Convenience',
  'Discount',
  'Express',
  'Other',
]

const GEMINI_MODELS = [
  { value: 'gemini-2.5-pro', label: '2.5 Pro — Most accurate (slower)' },
  { value: 'gemini-2.5-flash', label: '2.5 Flash — Fast & good (default)' },
  { value: 'gemini-2.0-flash', label: '2.0 Flash — Fastest (less accurate)' },
]

const SHELF_LOCATIONS = [
  'Juice Aisle \u2014 Chilled',
  'Dairy Section \u2014 Chilled',
  'Health Food Section',
  'Organic Section',
  'Smoothie Section \u2014 Chilled',
  'Chilled Section',
  'Ambient Aisle',
  'Other',
]

export default function MetadataForm({ metadata, photoCount, onAnalyze, onBack }) {
  const [form, setForm] = useState({ ...metadata, model: 'gemini-2.5-flash' })

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onAnalyze(form)
  }

  const isValid = form.country && form.retailer

  return (
    <div className="metadata-form card">
      <h2>Store Details</h2>
      <p className="description">
        Confirm or fill in the store metadata. Fields pre-filled from your file names are highlighted.
        At minimum, Country and Retailer are required.
      </p>
      <p className="photo-info">{photoCount} photo{photoCount !== 1 ? 's' : ''} ready for analysis</p>

      <form onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-group">
            <label>Country *</label>
            <input
              type="text"
              value={form.country}
              onChange={(e) => handleChange('country', e.target.value)}
              placeholder="e.g., Netherlands"
              className={metadata.country ? 'prefilled' : ''}
            />
          </div>

          <div className="form-group">
            <label>City</label>
            <input
              type="text"
              value={form.city}
              onChange={(e) => handleChange('city', e.target.value)}
              placeholder="e.g., Amsterdam"
              className={metadata.city ? 'prefilled' : ''}
            />
          </div>

          <div className="form-group">
            <label>Retailer *</label>
            <input
              type="text"
              value={form.retailer}
              onChange={(e) => handleChange('retailer', e.target.value)}
              placeholder="e.g., Albert Heijn"
              className={metadata.retailer ? 'prefilled' : ''}
            />
          </div>

          <div className="form-group">
            <label>Store Format</label>
            <select
              value={form.store_format}
              onChange={(e) => handleChange('store_format', e.target.value)}
              className={metadata.store_format ? 'prefilled' : ''}
            >
              <option value="">Select format...</option>
              {STORE_FORMATS.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Store Name</label>
            <input
              type="text"
              value={form.store_name}
              onChange={(e) => handleChange('store_name', e.target.value)}
              placeholder="e.g., AH Zuidas"
              className={metadata.store_name ? 'prefilled' : ''}
            />
          </div>

          <div className="form-group">
            <label>Shelf Location</label>
            <select
              value={form.shelf_location}
              onChange={(e) => handleChange('shelf_location', e.target.value)}
              className={metadata.shelf_location ? 'prefilled' : ''}
            >
              <option value="">Select location...</option>
              {SHELF_LOCATIONS.map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group form-full-width">
            <label>Gemini Model</label>
            <select
              value={form.model}
              onChange={(e) => handleChange('model', e.target.value)}
            >
              {GEMINI_MODELS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onBack}>
            Back
          </button>
          <button type="submit" className="btn btn-primary" disabled={!isValid}>
            Analyze {photoCount} Photo{photoCount !== 1 ? 's' : ''}
          </button>
        </div>
      </form>
    </div>
  )
}
