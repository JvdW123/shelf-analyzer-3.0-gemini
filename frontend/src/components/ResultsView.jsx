import { useState } from 'react'
import './ResultsView.css'

const DISPLAY_COLUMNS = [
  { key: 'photo', label: 'Photo' },
  { key: 'shelf_level', label: 'Level' },
  { key: 'brand', label: 'Brand' },
  { key: 'product_name', label: 'Product Name' },
  { key: 'flavor', label: 'Flavor' },
  { key: 'product_type', label: 'Type' },
  { key: 'facings', label: 'Facings' },
  { key: 'price_local', label: 'Price' },
  { key: 'packaging_size_ml', label: 'ml' },
  { key: 'packaging_type', label: 'Packaging' },
  { key: 'stock_status', label: 'Stock' },
  { key: 'confidence_score', label: 'Conf.' },
]

function ConfidenceBadge({ score }) {
  let className = 'badge '
  if (score >= 75) className += 'badge-green'
  else if (score >= 55) className += 'badge-yellow'
  else className += 'badge-red'
  return <span className={className}>{score}%</span>
}

function StockBadge({ status }) {
  const isOos = status === 'Out of Stock'
  return (
    <span className={`badge ${isOos ? 'badge-red' : 'badge-green'}`}>
      {isOos ? 'OOS' : 'In Stock'}
    </span>
  )
}

export default function ResultsView({ results, onDownloadExcel, onNewAnalysis }) {
  const [downloading, setDownloading] = useState(false)
  const { skus, sku_count, session_id } = results

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await onDownloadExcel()
    } finally {
      setDownloading(false)
    }
  }

  // Summary stats
  const brands = [...new Set(skus.map(s => s.brand).filter(Boolean))]
  const totalFacings = skus.reduce((sum, s) => sum + (s.facings || 0), 0)
  const oosCount = skus.filter(s => s.stock_status === 'Out of Stock').length
  const avgConfidence = skus.length
    ? Math.round(skus.reduce((sum, s) => sum + (s.confidence_score || 0), 0) / skus.length)
    : 0

  return (
    <div className="results-view">
      <div className="results-header card">
        <div className="results-summary">
          <h2>Analysis Complete</h2>
          <div className="stats-grid">
            <div className="stat">
              <span className="stat-value">{sku_count}</span>
              <span className="stat-label">SKUs found</span>
            </div>
            <div className="stat">
              <span className="stat-value">{brands.length}</span>
              <span className="stat-label">Brands</span>
            </div>
            <div className="stat">
              <span className="stat-value">{totalFacings}</span>
              <span className="stat-label">Total facings</span>
            </div>
            <div className="stat">
              <span className="stat-value">{oosCount}</span>
              <span className="stat-label">Out of stock</span>
            </div>
            <div className="stat">
              <span className="stat-value">{avgConfidence}%</span>
              <span className="stat-label">Avg confidence</span>
            </div>
          </div>
        </div>
        <div className="results-actions">
          <button className="btn btn-success" onClick={handleDownload} disabled={downloading}>
            {downloading ? 'Generating...' : 'Download Excel'}
          </button>
          <button className="btn btn-secondary" onClick={onNewAnalysis}>
            New Analysis
          </button>
        </div>
      </div>

      <div className="results-table-container card">
        <h3>SKU Preview ({sku_count} rows)</h3>
        <div className="table-scroll">
          <table className="results-table">
            <thead>
              <tr>
                <th>#</th>
                {DISPLAY_COLUMNS.map(col => (
                  <th key={col.key}>{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {skus.map((sku, index) => (
                <tr key={index} className={sku.stock_status === 'Out of Stock' ? 'row-oos' : ''}>
                  <td className="row-num">{index + 1}</td>
                  {DISPLAY_COLUMNS.map(col => (
                    <td key={col.key}>
                      {col.key === 'confidence_score' ? (
                        <ConfidenceBadge score={sku[col.key]} />
                      ) : col.key === 'stock_status' ? (
                        <StockBadge status={sku[col.key]} />
                      ) : (
                        sku[col.key] ?? ''
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="table-note">
          This preview shows key columns. The Excel download contains all 33 columns with full formatting.
        </p>
      </div>
    </div>
  )
}
