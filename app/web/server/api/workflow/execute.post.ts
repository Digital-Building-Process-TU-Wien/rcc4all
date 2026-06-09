import { exec } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import process from 'node:process'
import { promisify } from 'node:util'

const execAsync = promisify(exec)

export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  if (!body) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Workflow JSON is required',
    })
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
  const filename = `workflow-${timestamp}.json`
  const resultsFilename = `results-${timestamp}.json`
  const devFilesDir = join(process.cwd(), '.dev-files')
  const workflowPath = join(devFilesDir, filename)
  const resultsPath = join(devFilesDir, resultsFilename)

  try {
    await mkdir(devFilesDir, { recursive: true })
    await writeFile(workflowPath, JSON.stringify(body, null, 2), 'utf-8')

    const runnerDir = join(process.cwd(), '..', 'runner')
    const command = `uv run openbim-runner run "${workflowPath}"`

    const { stdout } = await execAsync(command, {
      cwd: runnerDir,
      maxBuffer: 10 * 1024 * 1024,
      timeout: 30000,
    })

    let results
    try {
      results = JSON.parse(stdout)
    }
    catch {
      results = { raw: stdout }
    }

    await writeFile(resultsPath, JSON.stringify({ success: true, results }, null, 2), 'utf-8')

    // stderr logged by runner if present

    return {
      success: true,
      workflowPath: filename,
      resultsPath: resultsFilename,
      results,
    }
  }
  catch (error: any) {
    // Error handled below

    const errorResults = {
      success: false,
      error: error.message || 'Unknown error occurred',
      stderr: error.stderr,
    }

    await writeFile(resultsPath, JSON.stringify(errorResults, null, 2), 'utf-8')

    return {
      success: false,
      workflowPath: filename,
      resultsPath: resultsFilename,
      error: error.message || 'Unknown error occurred',
      stderr: error.stderr,
    }
  }
})
