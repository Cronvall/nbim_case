import React from 'react'
import './LoadingComponent.css'

const LoadingComponent: React.FC = () => {
  return (
    <div className="loading-container">
      <div className="loading-content">
        <div className="loading-spinner">
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
        </div>
        <div className="loading-time-estimate">
          <span>⏱️ Estimated time: ~1 minute</span>
        </div>
      </div>
    </div>
  )
}

export default LoadingComponent
