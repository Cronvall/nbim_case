import React, { useLayoutEffect, useRef, useState } from 'react'

interface PipelineGraphProps {
  rawFields?: Record<string, any>
}

type Edge = { from: string; to: string; color?: string }

type EdgePos = { x1: number; y1: number; x2: number; y2: number; color?: string }

const PipelineGraph: React.FC<PipelineGraphProps> = ({ rawFields }) => {
  // Stages and fields
  const sourceFields = [
    'COAC_EVENT_KEY',
    'INSTRUMENT_DESCRIPTION',
    'ISIN',
    'SEDOL',
    'TICKER',
    'ORGANISATION_NAME',
    'DIVIDENDS_PER_SHARE',
    'EXDATE',
    'PAYMENT_DATE',
    'CUSTODIAN',
    'BANK_ACCOUNT',
    'QUOTATION_CURRENCY',
    'SETTLEMENT_CURRENCY',
    'NOMINAL_BASIS',
  ]

  const calcFields = [
    'AVG_FX_RATE_QUOTATION_TO_PORTFOLIO',
    'WTHTAX_RATE',
    'RESTITUTION_RATE',
    'TOTAL_TAX_RATE',
  ]

  const quotationFields = [
    'GROSS_AMOUNT_QUOTATION',
    'WTHTAX_COST_QUOTATION',
    'EXRESPRDIV_COST_QUOTATION',
    'LOCALTAX_COST_QUOTATION',
    'NET_AMOUNT_QUOTATION',
  ]

  const settlementFields = [
    'WTHTAX_COST_SETTLEMENT',
    'EXRESPRDIV_COST_SETTLEMENT',
    'LOCALTAX_COST_SETTLEMENT',
    'NET_AMOUNT_SETTLEMENT',
  ]

  const portfolioFields = [
    'GROSS_AMOUNT_PORTFOLIO',
    'NET_AMOUNT_PORTFOLIO',
    'WTHTAX_COST_PORTFOLIO',
  ]

  const edges: Edge[] = [
    { from: 'GROSS_AMOUNT_QUOTATION', to: 'NET_AMOUNT_QUOTATION', color: '#2563eb' },
    { from: 'WTHTAX_COST_QUOTATION', to: 'NET_AMOUNT_QUOTATION', color: '#ef4444' },
    { from: 'LOCALTAX_COST_QUOTATION', to: 'NET_AMOUNT_QUOTATION', color: '#f59e0b' },
    { from: 'EXRESPRDIV_COST_QUOTATION', to: 'NET_AMOUNT_QUOTATION', color: '#7c3aed' },
    { from: 'WTHTAX_RATE', to: 'WTHTAX_COST_QUOTATION', color: '#ef4444' },
    { from: 'GROSS_AMOUNT_QUOTATION', to: 'WTHTAX_COST_QUOTATION', color: '#ef4444' },
    { from: 'AVG_FX_RATE_QUOTATION_TO_PORTFOLIO', to: 'GROSS_AMOUNT_PORTFOLIO', color: '#059669' },
    { from: 'GROSS_AMOUNT_QUOTATION', to: 'GROSS_AMOUNT_PORTFOLIO', color: '#059669' },
    { from: 'AVG_FX_RATE_QUOTATION_TO_PORTFOLIO', to: 'NET_AMOUNT_PORTFOLIO', color: '#059669' },
    { from: 'NET_AMOUNT_QUOTATION', to: 'NET_AMOUNT_PORTFOLIO', color: '#059669' },
    { from: 'AVG_FX_RATE_QUOTATION_TO_PORTFOLIO', to: 'WTHTAX_COST_PORTFOLIO', color: '#059669' },
    { from: 'WTHTAX_COST_QUOTATION', to: 'WTHTAX_COST_PORTFOLIO', color: '#059669' },
    { from: 'WTHTAX_COST_SETTLEMENT', to: 'NET_AMOUNT_SETTLEMENT', color: '#ef4444' },
    { from: 'EXRESPRDIV_COST_SETTLEMENT', to: 'NET_AMOUNT_SETTLEMENT', color: '#7c3aed' },
    { from: 'LOCALTAX_COST_SETTLEMENT', to: 'NET_AMOUNT_SETTLEMENT', color: '#f59e0b' },
  ]

  const gridRef = useRef<HTMLDivElement | null>(null)
  const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [edgePositions, setEdgePositions] = useState<EdgePos[]>([])

  const renderNode = (label: string) => {
    const value = rawFields?.[label]
    return (
      <div
        className="node-card"
        key={label}
        ref={(el) => { nodeRefs.current[label] = el }}
        data-node={label}
        title={value !== undefined ? String(value) : undefined}
      >
        <div className="node-title">{label}</div>
        {value !== undefined && (
          <div className="node-value" title={String(value)}>
            {String(value)}
          </div>
        )}
      </div>
    )
  }

  const computePositions = () => {
    const container = gridRef.current
    if (!container) return
    const cRect = container.getBoundingClientRect()
    const positions: EdgePos[] = []
    for (const e of edges) {
      const fromEl = nodeRefs.current[e.from]
      const toEl = nodeRefs.current[e.to]
      if (!fromEl || !toEl) continue
      const fr = fromEl.getBoundingClientRect()
      const tr = toEl.getBoundingClientRect()
      const x1 = fr.right - cRect.left
      const y1 = fr.top + fr.height / 2 - cRect.top
      const x2 = tr.left - cRect.left
      const y2 = tr.top + tr.height / 2 - cRect.top
      positions.push({ x1, y1, x2, y2, color: e.color })
    }
    setEdgePositions(positions)
  }

  useLayoutEffect(() => {
    computePositions()
    const onResize = () => computePositions()
    window.addEventListener('resize', onResize)
    const container = gridRef.current
    const onScroll = () => computePositions()
    container?.addEventListener('scroll', onScroll)
    return () => {
      window.removeEventListener('resize', onResize)
      container?.removeEventListener('scroll', onScroll)
    }
  })

  return (
    <div className="pipeline-container">
      <svg className="pipeline-arrows">
        {edgePositions.map((p, i) => (
          <line
            key={i}
            x1={p.x1}
            y1={p.y1}
            x2={p.x2}
            y2={p.y2}
            stroke={p.color || '#64748b'}
            strokeWidth={2}
            markerEnd="url(#arrowhead)"
            opacity={0.9}
          />
        ))}
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">
            <polygon points="0 0, 8 4, 0 8" fill="#64748b" />
          </marker>
        </defs>
      </svg>

      <div className="pipeline-grid" ref={gridRef}>
        <div className="stage-column">
          <div className="stage-title">Source Inputs</div>
          <div className="stage-content">{sourceFields.map(renderNode)}</div>
        </div>
        <div className="stage-column">
          <div className="stage-title">Derived Calculations</div>
          <div className="stage-content">{calcFields.map(renderNode)}</div>
        </div>
        <div className="stage-column">
          <div className="stage-title">Quotation Amounts</div>
          <div className="stage-content">{quotationFields.map(renderNode)}</div>
        </div>
        <div className="stage-column">
          <div className="stage-title">Settlement Amounts</div>
          <div className="stage-content">{settlementFields.map(renderNode)}</div>
        </div>
        <div className="stage-column">
          <div className="stage-title">Portfolio Amounts</div>
          <div className="stage-content">{portfolioFields.map(renderNode)}</div>
        </div>
      </div>
    </div>
  )
}

export default PipelineGraph
