import { FormEvent, ReactNode, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, formatDate, jsonBody } from './api'
import { useAuth } from './AuthContext'
import { HelpTooltip, LabelHelp } from './HelpTooltip'
import type { AreaPreset, CatalogCheck, CatalogPreview, ImportRecord, RegistrySource } from './types'

const LAYER_TYPES = [
  'EGIB_PARCELS','EGIB_BUILDINGS','LPIS_REFERENCE_PARCELS','LPIS_MKO','LPIS_PZ','LPIS_GSA',
  'BDOT500_FENCES','BDOT10K','GESUT_NETWORKS','ADMIN_BOUNDARIES','GENERIC_POLYGON','GENERIC_LINE','GENERIC_POINT',
]

const modeLabels: Record<string,string> = {
  AUTOMATIC: 'Automatyczny',
  MANUAL_DOWNLOAD: 'Pobierz i wgraj',
  MANUAL_ORDER: 'Wymaga zamówienia',
  VIEW_ONLY: 'Tylko podgląd',
  MANUAL_UPLOAD: 'Plik użytkownika',
}

function ErrorMessage({ error }: { error: unknown }) {
  return error instanceof Error ? <p className="alert error">{error.message}</p> : null
}

function Status({ value }: { value: string }) {
  const hints: Record<string,string> = {
    IMPLEMENTED: 'Źródło ma skonfigurowany i zweryfikowany sposób użycia w aplikacji.',
    VIEW_ONLY: 'Usługa służy wyłącznie do oglądania mapy. Nie dostarcza geometrii do analiz.',
    TEMPORARILY_UNAVAILABLE: 'Endpoint był niedostępny podczas ostatniej kontroli i import jest zablokowany.',
    DONE: 'Import zakończył się i warstwa jest dostępna w projekcie.',
    ERROR: 'Import nie zakończył się poprawnie. Szczegóły są zapisane w historii i logach.',
  }
  return <span className={`status status-${value.toLowerCase()}`}>{value}{hints[value]&&<HelpTooltip text={hints[value]}/>}</span>
}

function linkified(text: string): ReactNode[] {
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g
  const nodes: ReactNode[] = []
  let cursor = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) nodes.push(text.slice(cursor, index))
    nodes.push(<a key={`${match[2]}-${index}`} href={match[2]} target="_blank" rel="noreferrer">{match[1]} ↗</a>)
    cursor = index + match[0].length
  }
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

function Instructions({ markdown }: { markdown?: string }) {
  if (!markdown) return null
  const steps = markdown.split('\n').map(line => line.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
  return <ol className="instructions">{steps.map((step, index) => <li key={`${index}-${step}`}>{linkified(step)}</li>)}</ol>
}

function CatalogCard({ source, selected, onSelect }: { source: RegistrySource; selected?: boolean; onSelect?: () => void }) {
  return <article className={`source-card ${selected ? 'selected' : ''} ${!source.is_active ? 'disabled' : ''}`}>
    <div className="source-card-heading">
      <div><p className="eyebrow">{source.provider || source.category}</p><h3>{source.name}</h3></div>
      <Status value={source.implementation_status}/>
    </div>
    <p>{source.description}</p>
    <div className="source-facts">
      <span><strong>Tryb</strong>{modeLabels[source.import_mode] || source.import_mode}</span>
      <span><strong>Geometria</strong>{source.geometry_type || 'zależna od pliku'}</span>
      <span><strong>Rocznik</strong>{source.dataset_version || 'bieżące źródło'}</span>
      <span><strong>Zakres</strong>{source.geographic_scope || 'nieokreślony'}</span>
    </div>
    {source.last_verified_at && <small>Weryfikacja: {formatDate(source.last_verified_at)}</small>}
    {onSelect && <button type="button" className={selected ? 'primary' : 'secondary'} onClick={onSelect}>{selected ? 'Wybrane źródło' : 'Wybierz i zobacz szczegóły'}</button>}
  </article>
}

export interface ImportArea {
  bbox: number[]
  label: string
}

function SourceDetails({ source, check, onCheck }: { source: RegistrySource; check?: CatalogCheck; onCheck: () => void }) {
  return <section className="panel source-details">
    <div className="source-card-heading"><div><p className="eyebrow">SZCZEGÓŁY ŹRÓDŁA</p><h2>{source.name}</h2></div><Status value={source.implementation_status}/></div>
    <p>{source.description}</p>
    {source.limitations && <p className="research-note compact"><strong>Ograniczenia:</strong> {source.limitations}</p>}
    {source.legal_note && <p className="research-note compact"><strong>Znaczenie badawcze:</strong> {source.legal_note}</p>}
    <Instructions markdown={source.instruction_md}/>
    <div className="actions source-links">
      {source.documentation_url && <a className="secondary button-link" href={source.documentation_url} target="_blank" rel="noreferrer">Dokumentacja ↗</a>}
      {source.service_type === 'WFS' && <button type="button" className="secondary" onClick={onCheck}>Sprawdź dostępność</button>}
    </div>
    {check && <p className={`alert ${check.status === 'AVAILABLE' ? 'success' : 'error'}`}>{check.message}</p>}
  </section>
}

export function ImportTab({
  projectId,
  area,
  onAreaChange,
  onSelectOnMap,
}: {
  projectId: string
  area: ImportArea | null
  onAreaChange: (area: ImportArea) => void
  onSelectOnMap: () => void
}) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [selectedKey, setSelectedKey] = useState('')
  const [manualProfileKey, setManualProfileKey] = useState('')
  const [preview, setPreview] = useState<CatalogPreview | null>(null)
  const [check, setCheck] = useState<CatalogCheck | undefined>()
  const catalog = useQuery({queryKey:['source-catalog'],queryFn:()=>api<RegistrySource[]>('/api/source-catalog')})
  const presets = useQuery({queryKey:['area-presets'],queryFn:()=>api<AreaPreset[]>('/api/source-catalog/area-presets')})
  const imports = useQuery({queryKey:['imports',projectId],queryFn:()=>api<ImportRecord[]>(`/api/projects/${projectId}/imports`)})
  const selected = catalog.data?.find(item => item.key === selectedKey)
  const manualProfile = catalog.data?.find(item => item.key === manualProfileKey)
  const automatic = catalog.data?.filter(item => item.import_mode === 'AUTOMATIC') ?? []
  const download = catalog.data?.filter(item => item.import_mode === 'MANUAL_DOWNLOAD') ?? []
  const order = catalog.data?.filter(item => item.import_mode === 'MANUAL_ORDER') ?? []

  const previewMutation = useMutation({
    mutationFn:()=>api<CatalogPreview>(`/api/projects/${projectId}/imports/catalog/preview`,{method:'POST',...jsonBody({source_key:selectedKey,bbox:area?.bbox})}),
    onSuccess:setPreview,
  })
  const importMutation = useMutation({
    mutationFn:()=>api<ImportRecord>(`/api/projects/${projectId}/imports/catalog`,{method:'POST',...jsonBody({source_key:selectedKey,bbox:area?.bbox})}),
    onSuccess:()=>{queryClient.invalidateQueries({queryKey:['layers',projectId]});queryClient.invalidateQueries({queryKey:['imports',projectId]});setPreview(null)},
  })
  const checkMutation = useMutation({
    mutationFn:(key:string)=>api<CatalogCheck>(`/api/source-catalog/${key}/check`,{method:'POST'}),
    onSuccess:value=>{setCheck(value);queryClient.invalidateQueries({queryKey:['source-catalog']})},
  })
  const fileMutation = useMutation({
    mutationFn:(body:FormData)=>api<ImportRecord>(`/api/projects/${projectId}/imports/file`,{method:'POST',body}),
    onSuccess:()=>{queryClient.invalidateQueries({queryKey:['layers',projectId]});queryClient.invalidateQueries({queryKey:['imports',projectId]})},
  })
  const fileSubmit=(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();fileMutation.mutate(new FormData(event.currentTarget))}
  const bboxSubmit=(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();const form=new FormData(event.currentTarget);const bbox=['min_lon','min_lat','max_lon','max_lat'].map(name=>Number(form.get(name)))
    if(bbox.every(Number.isFinite)&&bbox[0]<bbox[2]&&bbox[1]<bbox[3])onAreaChange({bbox,label:'BBOX wpisany ręcznie'})
  }
  const chooseSource=(key:string)=>{setSelectedKey(key);setManualProfileKey('');setPreview(null);setCheck(undefined)}

  if (user?.role === 'VIEWER') return <div className="empty">Rola VIEWER nie może importować danych.</div>
  return <div className="import-workspace">
    <section className="guided-intro">
      <div><p className="eyebrow">PROWADZONY IMPORT</p><h2>Wybierz zweryfikowane źródło</h2><p>GeoHarmonizer dobierze wersję WFS, format i kolejność osi. Ty wskazujesz tylko warstwę oraz obszar badania.</p></div>
      <HelpTooltip text="Każdy import zapisuje endpoint, wersję danych, zakres, datę kontroli i sumę SHA-256, aby badanie dało się odtworzyć."/>
    </section>

    <div className="catalog-layout">
      <section className="catalog-column">
        <h2>Automatyczny</h2>
        <p className="muted">Dane wektorowe pobierane bezpośrednio z oficjalnej usługi dla ograniczonego obszaru.</p>
        <div className="source-grid">{automatic.map(source=><CatalogCard key={source.key} source={source} selected={selectedKey===source.key} onSelect={()=>chooseSource(source.key)}/>)}</div>
        <h2>Pobierz i wgraj</h2>
        <p className="muted">Duże, wersjonowane paczki. Pobierasz je samodzielnie zgodnie z instrukcją.</p>
        <div className="source-grid">{download.map(source=><CatalogCard key={source.key} source={source} selected={selectedKey===source.key} onSelect={()=>{chooseSource(source.key);setManualProfileKey(source.key)}}/>)}</div>
        <h2>Wymaga zamówienia</h2>
        <p className="muted">Materiały powiatowe bez potwierdzonego publicznego pobierania.</p>
        <div className="source-grid">{order.map(source=><CatalogCard key={source.key} source={source} selected={selectedKey===source.key} onSelect={()=>{chooseSource(source.key);setManualProfileKey(source.key)}}/>)}</div>
      </section>

      <aside className="import-side">
        {selected ? <SourceDetails source={selected} check={check} onCheck={()=>checkMutation.mutate(selected.key)}/> : <div className="panel empty compact-empty">Wybierz źródło, aby zobaczyć parametry i instrukcje.</div>}
        {selected?.import_mode === 'AUTOMATIC' && selected.is_active && <section className="panel stack">
          <h2><LabelHelp label="Obszar importu" text="Ograniczenie przestrzenne chroni usługę zewnętrzną i aplikację przed przypadkowym pobraniem milionów obiektów."/></h2>
          <div className="preset-list">{presets.data?.map(preset=><button type="button" className="secondary" key={preset.key} onClick={()=>{onAreaChange({bbox:preset.bbox,label:preset.name});setPreview(null)}}>{preset.name}</button>)}</div>
          <button type="button" className="secondary" onClick={onSelectOnMap}>Narysuj prostokąt na mapie</button>
          {area ? <div className="area-summary"><strong>{area.label}</strong><code>{area.bbox.map(value=>value.toFixed(5)).join(', ')}</code></div> : <p className="alert error">Wybierz obszar przed sprawdzeniem danych.</p>}
          <details><summary>Zaawansowane: wpisz BBOX WGS84</summary><form className="bbox-form" onSubmit={bboxSubmit}>{['min_lon','min_lat','max_lon','max_lat'].map(name=><label key={name}>{name}<input name={name} type="number" step="any" required/></label>)}<button className="secondary">Zastosuj BBOX</button></form></details>
          <button type="button" className="primary" disabled={!area||previewMutation.isPending} onClick={()=>previewMutation.mutate()}>{previewMutation.isPending?'Sprawdzanie…':'Sprawdź zakres przed importem'}</button>
          <ErrorMessage error={previewMutation.error}/>
          {preview && <div className={`preview-box ${preview.allowed?'ok':'blocked'}`}><strong>{preview.estimated_feature_count == null?'Liczba obiektów nieznana':`${preview.estimated_feature_count} obiektów`}</strong><small>Limit: {preview.feature_limit}</small>{preview.warnings.map(message=><p key={message}>{message}</p>)}<button type="button" className="primary" disabled={!preview.allowed||importMutation.isPending} onClick={()=>importMutation.mutate()}>{importMutation.isPending?'Importowanie…':'Importuj zweryfikowany zakres'}</button></div>}
          <ErrorMessage error={importMutation.error}/>
        </section>}

        <section className="panel">
          <h2><LabelHelp label="Mam już plik" text="Wgraj wyłącznie plik uzyskany z opisanej usługi. Oryginalna nazwa, rozmiar i suma SHA-256 zostaną zapisane w metadanych importu."/></h2>
          <form key={manualProfile?.key||'manual'} className="stack" onSubmit={fileSubmit}>
            <input name="source_key" value={manualProfile?.key||''} readOnly type="hidden"/>
            <label>Plik<input name="file" type="file" accept=".geojson,.json,.gpkg,.zip,.gml" required /></label>
            <label>Nazwa warstwy<input name="layer_name" defaultValue={manualProfile?.name||''} required /></label>
            <label>Nazwa źródła<input name="source_name" defaultValue={manualProfile?.provider||manualProfile?.name||''} required /></label>
            <label><LabelHelp label="Profil danych" text="Profil opisuje znaczenie warstwy. Typ geometrii zostanie rozpoznany z pliku."/><select name="layer_type" defaultValue={manualProfile?.default_layer_type||'GENERIC_POLYGON'}>{LAYER_TYPES.map(value=><option key={value}>{value}</option>)}</select></label>
            <input name="target_crs" value="EPSG:2180" readOnly type="hidden"/>
            <button className="primary" disabled={fileMutation.isPending}>{fileMutation.isPending?'Importowanie…':'Wgraj plik'}</button>
          </form><ErrorMessage error={fileMutation.error}/>{fileMutation.isSuccess&&<p className="alert success">Import zakończony.</p>}
        </section>
      </aside>
    </div>

    <section className="import-history"><h2>Historia importów</h2>{imports.data?.length?<div className="timeline">{imports.data.map(item=><article key={item.id}><Status value={item.status}/><strong>{item.original_filename||'Źródło katalogowe'}</strong><small>{formatDate(item.created_at)} · {item.feature_count} obiektów</small>{item.error_message&&<p>{item.error_message}</p>}</article>)}</div>:<div className="empty">Brak importów.</div>}</section>
  </div>
}

export function SourcesTab() {
  const [category,setCategory]=useState('')
  const [mode,setMode]=useState('')
  const catalog=useQuery({queryKey:['source-catalog'],queryFn:()=>api<RegistrySource[]>('/api/source-catalog')})
  const current=useMemo(()=>(catalog.data??[]).filter(item=>item.provider),[catalog.data])
  const categories=useMemo(()=>Array.from(new Set(current.map(item=>item.category))).sort(),[current])
  const visible=current.filter(item=>(!category||item.category===category)&&(!mode||item.import_mode===mode))
  return <div className="catalog-page">
    <div className="guided-intro"><div><p className="eyebrow">KATALOG WIEDZY</p><h2>Zweryfikowane źródła danych</h2><p>Pozycje automatyczne dostarczają geometrię. WMS jest oznaczony jako podgląd i nie może zasilać analiz.</p></div><HelpTooltip text="Data weryfikacji mówi, kiedy faktycznie sprawdzono usługę. Dostępność zewnętrznych serwerów może się później zmienić."/></div>
    <div className="filters"><label>Kategoria<select value={category} onChange={event=>setCategory(event.target.value)}><option value="">Wszystkie</option>{categories.map(value=><option key={value}>{value}</option>)}</select></label><label>Tryb<select value={mode} onChange={event=>setMode(event.target.value)}><option value="">Wszystkie</option>{Object.entries(modeLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>
    <div className="source-grid knowledge-grid">{visible.map(source=><CatalogCard key={source.key} source={source}/>)}</div>
  </div>
}
