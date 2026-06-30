import { useEffect, useRef, useState } from 'react'
import Map from 'ol/Map'
import View from 'ol/View'
import GeoJSON from 'ol/format/GeoJSON'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import Draw, { createBox } from 'ol/interaction/Draw'
import { Fill, Stroke, Style, Circle as CircleStyle } from 'ol/style'
import { fromLonLat, transformExtent } from 'ol/proj'
import type { AnalysisRun, Layer } from './types'
import type { ImportArea } from './SourceCatalog'
import { HelpTooltip, LabelHelp } from './HelpTooltip'

const colors = ['#0f766e', '#c2410c', '#4338ca', '#be123c', '#047857', '#a16207']
const styleFor = (color: string) => new Style({ stroke: new Stroke({ color, width: 2 }), fill: new Fill({ color: `${color}22` }), image: new CircleStyle({ radius: 5, fill: new Fill({ color }), stroke: new Stroke({ color: '#fff', width: 1 }) }) })
const resultStyle = (feature: any) => {
  const severity = feature.get('severity')
  return styleFor(({ INFO: '#2563eb', LOW: '#16a34a', MEDIUM: '#d97706', HIGH: '#dc2626' } as Record<string,string>)[severity] ?? '#7c3aed')
}

export function MapView({ projectId, layers, runs, selectingImportArea = false, onImportAreaSelected, onCancelImportArea }: { projectId: string; layers: Layer[]; runs: AnalysisRun[]; selectingImportArea?: boolean; onImportAreaSelected?: (area: ImportArea) => void; onCancelImportArea?: () => void }) {
  const target = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map>()
  const vectorLayers = useRef<Record<string, VectorLayer<VectorSource>>>({})
  const resultLayer = useRef<VectorLayer<VectorSource>>()
  const selectionLayer = useRef<VectorLayer<VectorSource>>()
  const [visible, setVisible] = useState<Record<string,boolean>>(() => Object.fromEntries(layers.map(layer => [layer.id, layer.is_visible_by_default])))
  const [selected, setSelected] = useState<Record<string,unknown> | null>(null)
  const [selectedRun, setSelectedRun] = useState('')

  useEffect(() => {
    setVisible(current => {
      const next = { ...current }
      layers.forEach(layer => {
        if (!(layer.id in next)) next[layer.id] = layer.is_visible_by_default
      })
      return next
    })
  }, [layers])

  useEffect(() => {
    if (!target.current || mapRef.current) return
    const map = new Map({ target: target.current, layers: [], view: new View({ center: fromLonLat([19.1, 52.1]), zoom: 6 }) })
    resultLayer.current = new VectorLayer({ source: new VectorSource(), style: resultStyle })
    selectionLayer.current = new VectorLayer({ source: new VectorSource(), style: new Style({ stroke: new Stroke({ color: '#0e5553', width: 3, lineDash: [8, 5] }), fill: new Fill({ color: '#d9e89e44' }) }) })
    map.addLayer(resultLayer.current)
    map.addLayer(selectionLayer.current)
    map.on('singleclick', event => {
      const feature = map.forEachFeatureAtPixel(event.pixel, item => item)
      if (!feature) {
        setSelected(null)
        return
      }
      const properties = { ...feature.getProperties() }
      delete properties.geometry
      setSelected(properties)
    })
    mapRef.current = map
    return () => { map.setTarget(undefined); mapRef.current = undefined }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const source = selectionLayer.current?.getSource()
    if (!map || !source || !selectingImportArea) return
    source.clear()
    const draw = new Draw({ source, type: 'Circle', geometryFunction: createBox() })
    draw.on('drawstart', () => source.clear())
    draw.on('drawend', event => {
      const extent = event.feature.getGeometry()?.getExtent()
      if (!extent) return
      const bbox = transformExtent(extent, 'EPSG:3857', 'EPSG:4326')
      onImportAreaSelected?.({ bbox: Array.from(bbox), label: 'Prostokąt narysowany na mapie' })
    })
    map.addInteraction(draw)
    return () => { map.removeInteraction(draw) }
  }, [selectingImportArea, onImportAreaSelected])

  const useCurrentView = () => {
    const map = mapRef.current
    const size = map?.getSize()
    if (!map || !size) return
    const bbox = transformExtent(map.getView().calculateExtent(size), 'EPSG:3857', 'EPSG:4326')
    onImportAreaSelected?.({ bbox: Array.from(bbox), label: 'Aktualny widok mapy' })
  }

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    layers.forEach((layer, index) => {
      if (!vectorLayers.current[layer.id]) {
        const vector = new VectorLayer({ source: new VectorSource(), style: styleFor(colors[index % colors.length]), visible: visible[layer.id] ?? true })
        vector.set('name', layer.name)
        vectorLayers.current[layer.id] = vector
        map.getLayers().insertAt(index, vector)
        fetch(`/api/projects/${projectId}/layers/${layer.id}/features?limit=5000`, { credentials: 'include' }).then(response => response.json()).then(data => {
          const features = new GeoJSON().readFeatures(data, { dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' })
          vector.getSource()?.addFeatures(features)
          if (features.length && map.getView().getZoom() === 6) map.getView().fit(vector.getSource()!.getExtent(), { padding: [60,60,60,60], maxZoom: 18 })
        })
      }
      vectorLayers.current[layer.id].setVisible(visible[layer.id] ?? layer.is_visible_by_default)
    })
  }, [layers, projectId, visible])

  useEffect(() => {
    const source = resultLayer.current?.getSource()
    source?.clear()
    if (!selectedRun || !source) return
    fetch(`/api/projects/${projectId}/analysis-runs/${selectedRun}/results.geojson`, { credentials: 'include' }).then(response => response.json()).then(data => {
      const features = new GeoJSON().readFeatures(data, { dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' })
      source.addFeatures(features)
      if (features.length) mapRef.current?.getView().fit(source.getExtent(), { padding: [60,60,60,60], maxZoom: 18 })
    })
  }, [projectId, selectedRun])

  return <div className="map-layout">
    {selectingImportArea && <div className="map-selection-banner"><div><strong>Wybierz obszar importu</strong><small>Narysuj prostokąt na mapie albo użyj aktualnego widoku.</small></div><button type="button" className="secondary" onClick={useCurrentView}>Użyj aktualnego widoku</button><button type="button" className="secondary" onClick={onCancelImportArea}>Anuluj</button></div>}
    <aside className="map-sidebar">
      <h3>Warstwy projektu <HelpTooltip text="Włącz kilka warstw, aby porównać ich przebieg. Kliknięcie geometrii otwiera panel atrybutów."/></h3>
      {layers.length === 0 && <p className="muted">Brak warstw. Użyj zakładki Import.</p>}
      {layers.map(layer => <label className="layer-toggle" key={layer.id}><input type="checkbox" checked={visible[layer.id] ?? false} onChange={event => setVisible(current => ({ ...current, [layer.id]: event.target.checked }))}/><span>{layer.name}</span><small>{layer.feature_count}</small></label>)}
      <label><LabelHelp label="Wyniki analizy" text="Wybranie zakończonej analizy nakłada jej geometrie na mapę i automatycznie dopasowuje widok."/><select value={selectedRun} onChange={event => setSelectedRun(event.target.value)}><option value="">Bez wyników</option>{runs.filter(run => run.status === 'DONE').map(run => <option key={run.id} value={run.id}>{run.name}</option>)}</select></label>
      <div className="legend"><h4>Priorytet wyników <HelpTooltip text="Kolor oznacza priorytet przeglądu wyniku, a nie wiążącą ocenę prawną."/></h4><span className="dot info"/> INFO <span className="dot low"/> LOW <span className="dot medium"/> MEDIUM <span className="dot high"/> HIGH</div>
    </aside>
    <div className="map-canvas" ref={target} aria-label="Mapa projektu"/>
    {selected && <aside className="feature-panel"><button className="icon-button" onClick={() => setSelected(null)} aria-label="Zamknij">×</button><h3>Atrybuty obiektu</h3><pre>{JSON.stringify(selected, null, 2)}</pre></aside>}
  </div>
}
