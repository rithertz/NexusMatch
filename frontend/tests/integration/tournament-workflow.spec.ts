import { expect, test } from '@playwright/test'

const apiBase =
  process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api/v1'

test('creates, registers, brackets, and completes a persisted tournament', async ({
  page,
  request,
}) => {
  const suffix = Date.now().toString(36)
  const tournamentName = `Real Stack Cup ${suffix}`
  const competitorNames = [
    `Integration Player A ${suffix}`,
    `Integration Player B ${suffix}`,
    `Integration Player C ${suffix}`,
    `Integration Player D ${suffix}`,
  ]
  const players = []

  for (const [index, displayName] of competitorNames.entries()) {
    const response = await request.post(`${apiBase}/players`, {
      data: {
        username: `e2e_${suffix}_${index}`,
        display_name: displayName,
      },
    })
    expect(response.status()).toBe(201)
    players.push(await response.json())
  }

  const tournamentPayload = {
    game_name: 'Integration Test Game',
    tournament_type: 'individual',
    format: 'single_elimination',
    max_entries: 3,
  }
  const missingName = await request.post(`${apiBase}/tournaments`, {
    data: tournamentPayload,
  })
  expect(missingName.status()).toBe(422)
  const whitespaceName = await request.post(`${apiBase}/tournaments`, {
    data: { ...tournamentPayload, name: '   ' },
  })
  expect(whitespaceName.status()).toBe(422)
  const excessiveName = await request.post(`${apiBase}/tournaments`, {
    data: { ...tournamentPayload, name: 'N'.repeat(151) },
  })
  expect(excessiveName.status()).toBe(422)

  await page.goto('/organizer')
  await page.getByLabel('Name', { exact: true }).fill('')
  await page.getByLabel('Game', { exact: true }).fill('Integration Test Game')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByText('Enter a tournament name.', { exact: true })).toBeVisible()

  await page.getByLabel('Name', { exact: true }).fill('   ')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(
    page.getByText('Tournament name cannot be blank.'),
  ).toBeVisible()
  await expect(page.getByLabel('Name', { exact: true })).toHaveAttribute(
    'aria-invalid',
    'true',
  )

  await page.getByLabel('Name', { exact: true }).fill(`  ${tournamentName}  `)
  await page.getByLabel('Capacity').fill('3')
  const createResponsePromise = page.waitForResponse(
    response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/tournaments',
  )
  await page.getByRole('button', { name: 'Create draft' }).click()
  const createResponse = await createResponsePromise
  expect(createResponse.status()).toBe(201)
  const tournament = await createResponse.json()
  expect(tournament.name).toBe(tournamentName)
  expect(tournament.max_entries).toBe(3)
  await expect(page.getByText('Tournament created.')).toBeVisible()

  const closedRegistration = await request.post(`${apiBase}/registrations`, {
    data: {
      tournament_id: tournament.tournament_id,
      player_id: players[0].player_id,
    },
  })
  expect(closedRegistration.status()).toBe(409)

  await page.getByRole('link', { name: 'Discover' }).click()
  await expect(page.getByRole('heading', { name: tournamentName })).toBeVisible()
  const discoveryCard = page
    .locator('article.tcard')
    .filter({ has: page.getByRole('heading', { name: tournamentName }) })
  await discoveryCard.getByRole('link', { name: 'View tournament' }).click()
  await expect(page.getByRole('heading', { name: tournamentName, level: 1 })).toBeVisible()
  await expect(page.locator('.detail-head .status')).toHaveText('draft')

  await page.getByRole('link', { name: 'Organizer' }).click()
  const queue = page
    .locator('article.queue')
    .filter({ has: page.getByRole('link', { name: tournamentName }) })
  await queue.getByRole('button', { name: 'Open registration' }).click()
  await expect(page.getByText('Registration is now open.')).toBeVisible()

  await page.getByRole('link', { name: tournamentName }).click()
  await expect(page.locator('.detail-head .status')).toHaveText('registration open')
  for (const player of players.slice(0, 3)) {
    await page.locator('form.register select').selectOption(
      String(player.player_id),
    )
    const registrationResponsePromise = page.waitForResponse(
      response =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname === '/api/v1/registrations',
    )
    await page.getByRole('button', { name: 'Submit registration' }).click()
    const registrationResponse = await registrationResponsePromise
    expect(registrationResponse.status()).toBe(201)
  }

  const duplicateRegistration = await request.post(`${apiBase}/registrations`, {
    data: {
      tournament_id: tournament.tournament_id,
      player_id: players[0].player_id,
    },
  })
  expect(duplicateRegistration.status()).toBe(409)
  const overCapacityRegistration = await request.post(
    `${apiBase}/registrations`,
    {
      data: {
        tournament_id: tournament.tournament_id,
        player_id: players[3].player_id,
      },
    },
  )
  expect(overCapacityRegistration.status()).toBe(409)

  await page.getByRole('tab', { name: 'participants' }).click()
  for (const displayName of competitorNames.slice(0, 3)) {
    await expect(page.getByText(displayName, { exact: true })).toBeVisible()
  }

  await page.getByRole('link', { name: 'Organizer' }).click()
  const approvalQueue = page
    .locator('article.queue')
    .filter({ has: page.getByRole('link', { name: tournamentName }) })
  for (let index = 0; index < 3; index += 1) {
    await approvalQueue.getByRole('button', { name: 'Approve' }).first().click()
    await expect(approvalQueue.getByRole('button', { name: 'Approve' })).toHaveCount(
      2 - index,
    )
  }

  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Generate bracket' }).click()
  await expect(
    page.getByText('Bracket generated and tournament moved to in progress.'),
  ).toBeVisible()
  await page.getByRole('link', { name: tournamentName }).click()
  await page.getByRole('tab', { name: 'bracket' }).click()

  const bracketRegion = page.getByRole('region', {
    name: 'Single elimination bracket',
  })
  const firstRound = bracketRegion.locator('.round').first()
  const firstRoundMatches = firstRound.locator('button.match')
  await expect(firstRoundMatches).toHaveCount(2)
  const byeMatch = firstRoundMatches.filter({ hasText: 'Bye' })
  await expect(byeMatch).toHaveCount(1)
  const byeText = await byeMatch.innerText()
  const byeWinner = competitorNames.find(name => byeText.includes(name))
  if (!byeWinner) throw new Error('The persisted bye match has no participant name.')
  let playableMatch = firstRoundMatches.first()
  for (let index = 0; index < (await firstRoundMatches.count()); index += 1) {
    const candidate = firstRoundMatches.nth(index)
    if ((await candidate.locator(':scope > span').count()) === 2) {
      playableMatch = candidate
      break
    }
  }
  const playableMatchText = await playableMatch.innerText()
  const playableNames = competitorNames.filter(name =>
    playableMatchText.includes(name),
  )
  expect(playableNames).toHaveLength(2)
  const persistedBracketResponse = await request.get(
    `${apiBase}/tournaments/${tournament.tournament_id}/bracket`,
  )
  expect(persistedBracketResponse.status()).toBe(200)
  const persistedBracket = await persistedBracketResponse.json()
  const persistedMatch = persistedBracket.rounds[0].matches.find(
    match => !match.is_bye && match.participants.length === 2,
  )
  if (!persistedMatch) throw new Error('No playable persisted first-round match was found.')
  const persistedRegistrationIds = persistedMatch.participants.map(
    participant => participant.registration_id,
  )
  const invalidResult = await request.post(
    `${apiBase}/tournaments/${tournament.tournament_id}/matches/${persistedMatch.match_id}/result`,
    {
      data: {
        winner_registration_id: persistedRegistrationIds[0],
        scores: persistedRegistrationIds.map(registration_id => ({
          registration_id,
          score: 1,
        })),
      },
    },
  )
  expect(invalidResult.status()).toBe(422)
  await playableMatch.click()

  const resultDialog = page.getByRole('dialog', { name: /Match/ })
  await resultDialog.getByRole('spinbutton').nth(0).fill('1')
  await resultDialog.getByRole('spinbutton').nth(1).fill('1')
  await resultDialog.getByLabel('Winner').selectOption({
    label: playableNames[0],
  })
  await resultDialog.getByRole('button', { name: 'Confirm result' }).click()
  await expect(
    resultDialog.getByRole('alert'),
  ).toContainText('Enter two distinct non-negative scores')
  await resultDialog.getByRole('spinbutton').nth(0).fill('2')
  await resultDialog.getByRole('spinbutton').nth(1).fill('1')
  await resultDialog.getByLabel('Winner').selectOption({
    label: playableNames[0],
  })
  const firstResultPromise = page.waitForResponse(
    response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/result'),
  )
  await resultDialog.getByRole('button', { name: 'Confirm result' }).click()
  const firstResult = await firstResultPromise
  expect(firstResult.status()).toBe(200)

  const finalMatch = bracketRegion.locator('.round').nth(1).locator('button.match')
  await expect(finalMatch).toHaveCount(1)
  await expect(finalMatch).toContainText(byeWinner)
  await expect(finalMatch).toContainText(playableNames[0])
  await finalMatch.click()
  const finalDialog = page.getByRole('dialog', { name: /Match/ })
  await finalDialog.getByRole('spinbutton').nth(0).fill('1')
  await finalDialog.getByRole('spinbutton').nth(1).fill('3')
  await finalDialog.getByLabel('Winner').selectOption({
    label: playableNames[0],
  })
  const finalResultPromise = page.waitForResponse(
    response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/result'),
  )
  await finalDialog.getByRole('button', { name: 'Confirm result' }).click()
  const finalResult = await finalResultPromise
  expect(finalResult.status()).toBe(200)

  const repeatedBracket = await request.post(
    `${apiBase}/tournaments/${tournament.tournament_id}/bracket`,
  )
  expect(repeatedBracket.status()).toBe(409)
  const registrationAfterBracket = await request.post(
    `${apiBase}/registrations`,
    {
      data: {
        tournament_id: tournament.tournament_id,
        player_id: players[3].player_id,
      },
    },
  )
  expect(registrationAfterBracket.status()).toBe(409)

  await page.reload()
  await expect(page.getByRole('heading', { name: tournamentName, level: 1 })).toBeVisible()
  await expect(page.locator('.detail-head .status')).toHaveText('completed')
  await page.getByRole('tab', { name: 'bracket' }).click()
  await expect(bracketRegion.locator('.round').nth(1)).toContainText(
    playableNames[0],
  )
  await expect(bracketRegion.locator('.round').nth(1)).toContainText('3')
})

test('generates a simple bracket without byes against the live API', async ({
  page,
  request,
}) => {
  const suffix = Date.now().toString(36)
  const tournamentName = `No Bye Cup ${suffix}`
  const players = []

  for (let index = 0; index < 2; index += 1) {
    const response = await request.post(`${apiBase}/players`, {
      data: {
        username: `no_bye_${suffix}_${index}`,
        display_name: `No Bye Player ${index} ${suffix}`,
      },
    })
    expect(response.status()).toBe(201)
    players.push(await response.json())
  }

  const creation = await request.post(`${apiBase}/tournaments`, {
    data: {
      name: tournamentName,
      game_name: 'Integration Test Game',
      tournament_type: 'individual',
      format: 'single_elimination',
      max_entries: 2,
    },
  })
  expect(creation.status()).toBe(201)
  const tournament = await creation.json()
  const openRegistration = await request.patch(
    `${apiBase}/tournaments/${tournament.tournament_id}`,
    { data: { status: 'registration_open' } },
  )
  expect(openRegistration.status()).toBe(200)

  for (const player of players) {
    const registrationResponse = await request.post(`${apiBase}/registrations`, {
      data: {
        tournament_id: tournament.tournament_id,
        player_id: player.player_id,
      },
    })
    expect(registrationResponse.status()).toBe(201)
    const registration = await registrationResponse.json()
    const approval = await request.patch(
      `${apiBase}/registrations/${registration.registration_id}/status`,
      { data: { status: 'approved' } },
    )
    expect(approval.status()).toBe(200)
  }

  await page.goto('/organizer')
  const queue = page
    .locator('article.queue')
    .filter({ has: page.getByRole('link', { name: tournamentName }) })
  page.once('dialog', dialog => dialog.accept())
  await queue.getByRole('button', { name: 'Generate bracket' }).click()
  await expect(
    page.getByText('Bracket generated and tournament moved to in progress.'),
  ).toBeVisible()
  await page.getByRole('link', { name: tournamentName }).click()
  await page.getByRole('tab', { name: 'bracket' }).click()

  const bracket = page.getByRole('region', {
    name: 'Single elimination bracket',
  })
  await expect(bracket.locator('.round')).toHaveCount(1)
  await expect(bracket.locator('button.match')).toHaveCount(1)
  await expect(bracket.locator('button.match.bye')).toHaveCount(0)
  await expect(bracket.locator('button.match span')).toHaveCount(2)

  await page.reload()
  await page.getByRole('tab', { name: 'bracket' }).click()
  await expect(bracket.locator('.round')).toHaveCount(1)
  await expect(bracket.locator('button.match.bye')).toHaveCount(0)
})
