import { describe, expect, it } from 'vitest'
import { MAP_LAYER_Z_INDEX, projectLayerZIndex } from './mapLayers'

describe('kolejność warstw mapy', () => {
  it('zawsze umieszcza dane projektu i wyniki nad podkładem', () => {
    expect(projectLayerZIndex(0)).toBeGreaterThan(MAP_LAYER_Z_INDEX.base)
    expect(MAP_LAYER_Z_INDEX.results).toBeGreaterThan(projectLayerZIndex(100))
    expect(MAP_LAYER_Z_INDEX.selection).toBeGreaterThan(MAP_LAYER_Z_INDEX.results)
  })
})
