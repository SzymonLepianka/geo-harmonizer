export const MAP_LAYER_Z_INDEX = {
  base: 0,
  projectStart: 100,
  results: 10_000,
  selection: 20_000,
} as const

export const projectLayerZIndex = (index: number) => MAP_LAYER_Z_INDEX.projectStart + index
