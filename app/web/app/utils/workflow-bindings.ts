import type { Node } from '@vue-flow/core'
import type { NodeData, StoredEdge, StoredNode } from './nodes'
import type { PortNode, PortResolutionContext } from '~/schemas'
import {
  arePortsCompatible,
  getNodeInputs,
  getNodeOutputs,
  INPUT_HANDLE_PREFIX,
  isModelInput,
  parsePortHandle,
} from '~/schemas'

export type BindingNode = Node<NodeData> | StoredNode

export type OutputMatch
  = | { kind: 'matched', output: string }
    | { kind: 'ambiguous', candidates: string[] }
    | { kind: 'incompatible' }

export type AutoBindStatus = 'bound' | 'ambiguous' | 'incompatible' | 'no-op'

export interface AutoBindResult {
  bindings: Record<string, string>
  status: AutoBindStatus
  ambiguousInputs: string[]
  ambiguousOutputs: string[]
}

export interface AutoBindOptions {
  explicitOutput?: string
  explicitInput?: string
  context?: PortResolutionContext
}

export function splitReference(reference: string): [string, string] | null {
  const index = reference.indexOf('.')
  if (index <= 0 || index === reference.length - 1)
    return null
  return [reference.slice(0, index), reference.slice(index + 1)]
}

export function moveBindingReference(
  node: BindingNode,
  sourceId: string,
  oldField: string,
  newField: string,
): void {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    const parsed = splitReference(reference)
    if (parsed && parsed[0] === sourceId && parsed[1] === oldField)
      bindings[inputName] = `${sourceId}.${newField}`
  }
}

export function removeBindingReference(
  node: BindingNode,
  sourceId: string,
  fieldName: string,
): void {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    const parsed = splitReference(reference)
    if (parsed && parsed[0] === sourceId && parsed[1] === fieldName)
      delete bindings[inputName]
  }
}

/** Every binding on `node` that points at `sourceId` is dropped. */
export function clearBindingsFrom(node: BindingNode, sourceId: string): void {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    const parsed = splitReference(reference)
    if (parsed && parsed[0] === sourceId)
      delete bindings[inputName]
  }
}

/**
 * Pick an unambiguous compatible output from `sourceNode` for `targetNode`'s
 * `inputName`. Follows Python's exported compatibility table strictly:
 * - 0 compatible outputs → incompatible
 * - 1 compatible output → matched
 * - >1 compatible outputs with an exact port-name match → matched
 * - otherwise → ambiguous (never guesses by field order)
 */
export function matchCompatibleOutput(
  sourceNode: PortNode,
  targetNode: PortNode,
  inputName: string,
  candidateOutputs: string[] = getNodeOutputs(sourceNode),
  context?: PortResolutionContext,
): OutputMatch {
  const compatible = candidateOutputs.filter(output =>
    arePortsCompatible(targetNode, inputName, sourceNode, output, context),
  )
  if (compatible.length === 0)
    return { kind: 'incompatible' }
  if (compatible.length === 1)
    return { kind: 'matched', output: compatible[0]! }
  if (compatible.includes(inputName))
    return { kind: 'matched', output: inputName }
  return { kind: 'ambiguous', candidates: compatible }
}

/**
 * Resolve explicit input bindings to apply when wiring `sourceNode` → `targetNode`.
 *
 * Only strictly unambiguous matches are bound:
 * 1. Exact port-name matches whose types are compatible.
 * 2. Remaining type-compatible pairs where the input has only one compatible
 *    output and that output has only one compatible input.
 *
 * Any ambiguous routing is left blank and reported so the UI can warn the user.
 */
export function resolveAutoBindings(
  sourceId: string,
  sourceNode: PortNode,
  targetNode: PortNode,
  options: AutoBindOptions = {},
): AutoBindResult {
  const empty: AutoBindResult = {
    bindings: {},
    status: 'no-op',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  }

  const sourceOutputs = getNodeOutputs(sourceNode)
  const targetInputs = getNodeInputs(targetNode)
  if (sourceOutputs.length === 0 || targetInputs.length === 0)
    return empty

  const explicitOutput = options.explicitOutput && sourceOutputs.includes(options.explicitOutput)
    ? options.explicitOutput
    : undefined
  const explicitInput = options.explicitInput && targetInputs.includes(options.explicitInput)
    ? options.explicitInput
    : undefined
  const candidateOutputs = explicitOutput ? [explicitOutput] : sourceOutputs

  // Target handle names a specific port (subworkflow / subworkflow_output).
  if (explicitInput) {
    const match = matchCompatibleOutput(sourceNode, targetNode, explicitInput, candidateOutputs, options.context)
    if (match.kind === 'matched') {
      return {
        bindings: { [explicitInput]: `${sourceId}.${match.output}` },
        status: 'bound',
        ambiguousInputs: [],
        ambiguousOutputs: [],
      }
    }
    if (match.kind === 'ambiguous') {
      return {
        bindings: {},
        status: 'ambiguous',
        ambiguousInputs: [explicitInput],
        ambiguousOutputs: match.candidates,
      }
    }
    // Deliberate port-to-port wire (`output:a` -> `input:b`) stays recorded so
    // the port shows its exact type-mismatch warning.
    if (explicitOutput) {
      return {
        bindings: { [explicitInput]: `${sourceId}.${explicitOutput}` },
        status: 'bound',
        ambiguousInputs: [],
        ambiguousOutputs: [],
      }
    }
    return {
      bindings: {},
      status: 'incompatible',
      ambiguousInputs: [],
      ambiguousOutputs: [],
    }
  }

  const currentBindings = targetNode.data?.input_bindings ?? {}

  // A File Input emits a model slug and should only auto-wire into model-slug
  // ports unless the user targeted an explicit subworkflow port above.
  if (sourceNode.data?.nodeName === 'file_input') {
    const modelInputs = targetInputs.filter(isModelInput)
    if (modelInputs.length === 0) {
      return {
        bindings: {},
        status: 'incompatible',
        ambiguousInputs: [],
        ambiguousOutputs: [],
      }
    }
    const unbound = modelInputs.filter(name => !currentBindings[name])
    const pool = unbound.length > 0 ? unbound : modelInputs
    if (pool.length > 1) {
      return {
        bindings: {},
        status: 'ambiguous',
        ambiguousInputs: pool,
        ambiguousOutputs: candidateOutputs,
      }
    }
    const match = matchCompatibleOutput(sourceNode, targetNode, pool[0]!, candidateOutputs, options.context)
    if (match.kind === 'matched') {
      return {
        bindings: { [pool[0]!]: `${sourceId}.${match.output}` },
        status: 'bound',
        ambiguousInputs: [],
        ambiguousOutputs: [],
      }
    }
    return {
      bindings: {},
      status: match.kind,
      ambiguousInputs: match.kind === 'ambiguous' ? [pool[0]!] : [],
      ambiguousOutputs: match.kind === 'ambiguous' ? match.candidates : [],
    }
  }

  const hasModelOutput = candidateOutputs.some(isModelInput)
  const eligibleInputs = targetInputs.filter(name =>
    !currentBindings[name] && (!isModelInput(name) || hasModelOutput),
  )
  if (eligibleInputs.length === 0)
    return empty

  const bindings: Record<string, string> = {}
  const usedInputs = new Set<string>()
  const usedOutputs = new Set<string>()

  // Pass 1: exact port-name matches that satisfy Python's type rules.
  for (const inputName of eligibleInputs) {
    if (
      candidateOutputs.includes(inputName)
      && arePortsCompatible(targetNode, inputName, sourceNode, inputName, options.context)
    ) {
      bindings[inputName] = `${sourceId}.${inputName}`
      usedInputs.add(inputName)
      usedOutputs.add(inputName)
    }
  }

  // Pass 2: remaining type-compatible pairs; bind only strict 1-to-1 matches.
  const remainingInputs = eligibleInputs.filter(name => !usedInputs.has(name))
  const remainingOutputs = candidateOutputs.filter(name => !usedOutputs.has(name))
  const pairs: Array<[string, string]> = []
  const inputDegree = new Map<string, number>()
  const outputDegree = new Map<string, number>()

  for (const inputName of remainingInputs) {
    for (const outputName of remainingOutputs) {
      if (!arePortsCompatible(targetNode, inputName, sourceNode, outputName, options.context))
        continue
      pairs.push([inputName, outputName])
      inputDegree.set(inputName, (inputDegree.get(inputName) ?? 0) + 1)
      outputDegree.set(outputName, (outputDegree.get(outputName) ?? 0) + 1)
    }
  }

  const ambiguousInputs = new Set<string>()
  const ambiguousOutputs = new Set<string>()

  for (const [inputName, outputName] of pairs) {
    if (inputDegree.get(inputName) === 1 && outputDegree.get(outputName) === 1) {
      bindings[inputName] = `${sourceId}.${outputName}`
    }
    else {
      ambiguousInputs.add(inputName)
      ambiguousOutputs.add(outputName)
    }
  }

  const status: AutoBindStatus = ambiguousInputs.size > 0
    ? 'ambiguous'
    : Object.keys(bindings).length > 0
      ? 'bound'
      : 'incompatible'

  return {
    bindings,
    status,
    ambiguousInputs: [...ambiguousInputs],
    ambiguousOutputs: [...ambiguousOutputs],
  }
}

/**
 * Drop stale input bindings on targets of removed canvas edges so the user can
 * rewire cleanly. Explicit port edges only clear their own port; generic edges
 * clear all bindings from that source once no edge remains between the pair.
 */
export function pruneBindingsForRemovedEdges(
  nodesById: Record<string, BindingNode>,
  removedEdges: Pick<StoredEdge, 'source' | 'target' | 'targetHandle'>[],
  remainingEdges: Pick<StoredEdge, 'source' | 'target' | 'targetHandle'>[],
): void {
  for (const removed of removedEdges) {
    const targetNode = nodesById[removed.target]
    const bindings = targetNode?.data?.input_bindings
    if (!targetNode || !bindings)
      continue

    const explicitInput = parsePortHandle(removed.targetHandle, INPUT_HANDLE_PREFIX)
    if (explicitInput) {
      const stillConnected = remainingEdges.some(edge =>
        edge.source === removed.source
        && edge.target === removed.target
        && edge.targetHandle === removed.targetHandle,
      )
      if (!stillConnected) {
        const parsed = splitReference(bindings[explicitInput] ?? '')
        if (parsed && parsed[0] === removed.source)
          delete bindings[explicitInput]
      }
      continue
    }

    const stillConnected = remainingEdges.some(edge =>
      edge.source === removed.source && edge.target === removed.target,
    )
    if (!stillConnected)
      clearBindingsFrom(targetNode, removed.source)
  }
}
