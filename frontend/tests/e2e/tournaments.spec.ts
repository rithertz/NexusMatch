import { expect, test, type Page, type Route } from '@playwright/test'

const apiPattern = '**/api/v1/**'
const tournament = {
  tournament_id: 42,
  name: 'Nexus Invitational',
  game_name: 'Valorant',
  tournament_type: 'individual',
  format: 'single_elimination',
  status: 'registration_open',
  max_entries: 8,
  starts_at: null,
  created_at: '2026-10-13T00:00:00Z',
}

const registrations = [
  {
    registration_id: 71,
    tournament_id: 42,
    player_id: 11,
    team_id: null,
    status: 'approved',
    registered_at: '2026-10-13T00:10:00Z',
  },
  {
    registration_id: 72,
    tournament_id: 42,
    player_id: 12,
    team_id: null,
    status: 'pending',
    registered_at: '2026-10-13T00:11:00Z',
  },
]

const players = [
  {
    player_id: 11,
    username: 'arc',
    display_name: 'Arc Nova',
    email: null,
    created_at: '2026-10-13T00:00:00Z',
  },
  {
    player_id: 12,
    username: 'flare',
    display_name: 'Flare Echo',
    email: null,
    created_at: '2026-10-13T00:00:00Z',
  },
]

const bracket = {
  tournament_id: 42,
  rounds: [
    {
      round_number: 1,
      matches: [
        {
          match_id: 301,
          round_number: 1,
          match_number: 1,
          status: 'completed',
          is_bye: true,
          scheduled_at: null,
          started_at: null,
          completed_at: null,
          winner_registration_id: null,
          participants: [
            {
              registration_id: 71,
              slot_number: 1,
              competitor_type: 'player',
              competitor_id: 11,
              display_name: 'Arc Nova',
              score: null,
              is_winner: false,
            },
          ],
        },
        {
          match_id: 302,
          round_number: 1,
          match_number: 2,
          status: 'scheduled',
          is_bye: false,
          scheduled_at: null,
          started_at: null,
          completed_at: null,
          winner_registration_id: null,
          participants: [
            {
              registration_id: 72,
              slot_number: 1,
              competitor_type: 'player',
              competitor_id: 12,
              display_name: 'Flare Echo',
              score: null,
              is_winner: false,
            },
            {
              registration_id: 73,
              slot_number: 2,
              competitor_type: 'player',
              competitor_id: 13,
              display_name: 'Vector',
              score: null,
              is_winner: false,
            },
          ],
        },
      ],
    },
    {
      round_number: 2,
      matches: [
        {
          match_id: 303,
          round_number: 2,
          match_number: 1,
          status: 'scheduled',
          is_bye: false,
          scheduled_at: null,
          started_at: null,
          completed_at: null,
          winner_registration_id: null,
          participants: [
            {
              registration_id: 71,
              slot_number: 1,
              competitor_type: 'player',
              competitor_id: 11,
              display_name: 'Arc Nova',
              score: null,
              is_winner: false,
            },
          ],
        },
      ],
    },
  ],
}

type MockOptions = {
  tournaments?: unknown[]
  tournament?: unknown
  registrations?: unknown[]
  players?: unknown[]
  teams?: unknown[]
  bracket?: unknown
  bracketStatus?: number
  tournamentStatus?: number
  delayTournaments?: Promise<void>
}

async function mockApi(page: Page, options: MockOptions = {}) {
  await page.route(apiPattern, async (route: Route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')

    if (path === '/health') {
      await route.fulfill({
        json: {
          status: 'ok',
          checks: { postgres: 'ok', mongodb: 'ok' },
        },
      })
      return
    }
    if (path === '/tournaments' && route.request().method() === 'GET') {
      if (options.delayTournaments) await options.delayTournaments
      await route.fulfill({ json: options.tournaments ?? [tournament] })
      return
    }
    if (path === `/tournaments/${tournament.tournament_id}`) {
      await route.fulfill({
        status: options.tournamentStatus ?? 200,
        json:
          options.tournamentStatus && options.tournamentStatus >= 400
            ? { detail: 'Tournament service is unavailable.' }
            : options.tournament ?? tournament,
      })
      return
    }
    if (path === `/tournaments/${tournament.tournament_id}/bracket`) {
      await route.fulfill({
        status: options.bracketStatus ?? 200,
        json:
          options.bracketStatus && options.bracketStatus >= 400
            ? { detail: 'The tournament bracket has not been generated.' }
            : options.bracket ?? bracket,
      })
      return
    }
    if (path === '/players') {
      await route.fulfill({ json: options.players ?? players })
      return
    }
    if (path === '/teams') {
      await route.fulfill({ json: options.teams ?? [] })
      return
    }
    if (path === '/registrations') {
      await route.fulfill({ json: options.registrations ?? registrations })
      return
    }

    await route.fulfill({ status: 404, json: { detail: 'Not found.' } })
  })
}

test('application starts and renders tournament discovery without a fatal browser error', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await mockApi(page)

  await page.goto('/')

  await expect(
    page.getByRole('heading', { name: /find the next decisive match/i }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Nexus Invitational' })).toBeVisible()
  expect(pageErrors).toEqual([])
})

test('tournament overview shows the persisted tournament details', async ({ page }) => {
  await mockApi(page)

  await page.goto('/tournaments/42')

  await expect(
    page.getByRole('heading', { name: 'Nexus Invitational' }),
  ).toBeVisible()
  await expect(page.getByText('Competition briefing')).toBeVisible()
  await expect(page.getByText('Entry limit')).toBeVisible()
  await expect(page.getByText('registration open', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Register a individual' })).toBeVisible()
})

test('participants show player display names and the bracket renders rounds and byes', async ({
  page,
}) => {
  await mockApi(page)

  await page.goto('/tournaments/42')
  await page.getByRole('tab', { name: 'participants' }).click()

  await expect(page.getByText('Arc Nova')).toBeVisible()
  await expect(page.getByText('Flare Echo')).toBeVisible()
  await expect(page.getByText('Player #11')).toHaveCount(0)

  await page.getByRole('tab', { name: 'bracket' }).click()
  await expect(page.getByRole('region', { name: 'Single elimination bracket' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Round 1' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Final' })).toBeVisible()
  await expect(page.getByText('Match 1 · Bye')).toBeVisible()
  await expect(page.locator('.round').nth(1).getByText('Arc Nova')).toBeVisible()
  await expect(page.getByText('Vector')).toBeVisible()
})

test('team participants show team names rather than team IDs', async ({ page }) => {
  await mockApi(page, {
    tournament: { ...tournament, tournament_type: 'team' },
    registrations: [
      {
        registration_id: 91,
        tournament_id: 42,
        player_id: null,
        team_id: 31,
        status: 'approved',
        registered_at: '2026-10-13T00:10:00Z',
      },
    ],
    teams: [{ team_id: 31, team_name: 'Northstar', created_at: '2026-10-13T00:00:00Z' }],
  })

  await page.goto('/tournaments/42')
  await page.getByRole('tab', { name: 'participants' }).click()

  await expect(page.getByText('Northstar')).toBeVisible()
  await expect(page.getByText('Team #31')).toHaveCount(0)
})

test('tournament and participant empty states are explicit', async ({ page }) => {
  await mockApi(page, { tournaments: [], registrations: [], players: [] })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'No tournaments match' })).toBeVisible()

  await page.goto('/tournaments/42')
  await page.getByRole('tab', { name: 'participants' }).click()
  await expect(page.getByRole('heading', { name: 'No registrations yet' })).toBeVisible()
})

test('loading and API-error states are visible to users', async ({ page }) => {
  let releaseTournaments!: () => void
  const tournamentsGate = new Promise<void>(resolve => {
    releaseTournaments = resolve
  })
  await mockApi(page, { delayTournaments: tournamentsGate })

  await page.goto('/')
  await expect(page.getByText('Loading competition data…')).toBeVisible()
  releaseTournaments()
  await expect(page.getByRole('heading', { name: 'Nexus Invitational' })).toBeVisible()

  await mockApi(page, { tournamentStatus: 503 })
  await page.goto('/tournaments/42')
  await expect(page.getByRole('alert')).toContainText('Tournament service is unavailable.')
})

test('missing bracket is rendered as an explanatory empty state', async ({ page }) => {
  await mockApi(page, { bracketStatus: 404 })

  await page.goto('/tournaments/42')
  await page.getByRole('tab', { name: 'bracket' }).click()
  await expect(page.getByText('No persisted bracket yet.')).toBeVisible()
})
