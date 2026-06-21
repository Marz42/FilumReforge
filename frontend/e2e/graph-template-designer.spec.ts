import { expect, test } from './fixtures'

import { designerTemplateId, installGraphTemplateDesignerMock } from './graph-template-designer-mock'

test.beforeEach(async ({ mockApi, page }) => {
  await mockApi()
  await installGraphTemplateDesignerMock(page)
})

test('loads designer, validates, saves draft, and opens dry-run dialog', async ({ page }) => {
  await page.goto(`/task-templates/${designerTemplateId}/edit`)

  await expect(page.getByTestId('graph-template-designer')).toBeVisible()
  await expect(page.getByText('选题会（批次）')).toBeVisible()
  await expect(page.getByTestId('graph-template-dag-preview')).toBeVisible()

  await page.getByTestId('designer-validate').click()
  await expect(page.getByText('校验通过')).toBeVisible()

  await page.getByTestId('designer-dry-run').click()
  await expect(page.getByTestId('designer-dry-run-dialog')).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByTestId('designer-save').click()
  await expect(page.getByText('草稿已保存')).toBeVisible()
})

test('navigates from template list design action to designer', async ({ page }) => {
  await page.route('**/api/v1/workflow-graph/templates?**', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: designerTemplateId,
          code: 'topic_meeting_batch_v1',
          name: '选题会（批次）',
          status: 'draft',
          version: 2,
          run_kind: 'batch',
          config: {},
        },
      ]),
    })
  })

  await page.goto('/task-templates')
  await page.getByTestId('graph-template-design').first().click()
  await expect(page).toHaveURL(new RegExp(`/task-templates/${designerTemplateId}/edit`))
  await expect(page.getByTestId('graph-template-designer')).toBeVisible()
})
