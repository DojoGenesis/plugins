// Synthetic fixture: three agent() calls, one of them names no model.
export const meta = { name: 'fixture-mixed', description: 'one unpinned' }

const a = await agent('Scout the area.', { label: 'scout', model: 'haiku' })

const b = await agent('Build the thing.', { label: 'builder' })

const c = await agent('Judge the result.', { label: 'judge', model: 'opus' })
