// Synthetic fixture: every agent() call names a model. The word agent( in this comment is not a call.
export const meta = { name: 'fixture-clean', description: 'all pinned' }

const notes = JSON.stringify({ model: 'not-an-option', goal: args.goal })

const scout = await agent(
  'Look around and report. Context: ' + JSON.stringify({ goal: args.goal, tracks: args.tracks }) +
    (args.deep ? ' Go deeper.' : ' Keep it short.'),
  {
    label: 'scout',
    model: 'haiku',
    schema: { type: 'object', properties: { found: { type: 'string' } } },
  },
)

const build = await agent('Build it. ' + notes, { label: 'build', 'model': args.big ? 'opus' : 'sonnet' })

const judge = await agent(`Judge ${scout.found} against ${build}`, { label: 'judge', "model": 'opus' })
