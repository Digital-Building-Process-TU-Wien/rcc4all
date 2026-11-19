/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/* eslint-disable ts/no-use-before-define */

import type { ModelFile, NodePosition, PortArray, PortScalar, PortType, PortUnion, SubworkflowDefinition, SubworkflowPort, WorkflowDefinition, WorkflowEdge, WorkflowNode } from './workflow-schema'
import { z } from 'zod'

export const ModelFileSchema: z.ZodType<ModelFile> = z.lazy(() => z.object({ path: z.string(), slug: z.string(), hash: z.string().optional() }).strict())

export const NodePositionSchema: z.ZodType<NodePosition> = z.lazy(() => z.object({ x: z.number().optional(), y: z.number().optional() }).strict())

export const PortArraySchema: z.ZodType<PortArray> = z.lazy(() => z.object({ type: z.literal('array'), items: z.union([PortScalarSchema, PortArraySchema, PortUnionSchema]) }).strict())

export const PortScalarSchema: z.ZodType<PortScalar> = z.lazy(() => z.object({ type: z.enum(['string', 'integer', 'number', 'boolean', 'object', 'any']) }).strict())

export const PortTypeSchema: z.ZodType<PortType> = z.lazy(() => z.union([PortScalarSchema, PortArraySchema, PortUnionSchema]))

export const PortUnionSchema: z.ZodType<PortUnion> = z.lazy(() => z.object({ type: z.literal('union'), members: z.array(z.union([PortScalarSchema, PortArraySchema, PortUnionSchema])) }).strict())

export const SubworkflowDefinitionSchema: z.ZodType<SubworkflowDefinition> = z.lazy(() => z.object({ name: z.string().optional(), nodes: z.array(WorkflowNodeSchema).optional(), edges: z.array(WorkflowEdgeSchema).optional() }).strict())

export const SubworkflowPortSchema: z.ZodType<SubworkflowPort> = z.lazy(() => z.object({ name: z.string(), type: PortTypeSchema }).strict())

export const WorkflowDefinitionSchema: z.ZodType<WorkflowDefinition> = z.lazy(() => z.object({ files: z.array(ModelFileSchema).optional(), nodes: z.array(WorkflowNodeSchema).optional(), edges: z.array(WorkflowEdgeSchema).optional() }).strict())

export const WorkflowEdgeSchema: z.ZodType<WorkflowEdge> = z.lazy(() => z.object({ source: z.string(), target: z.string() }).strict())

export const WorkflowNodeSchema: z.ZodType<WorkflowNode> = z.lazy(() => z.object({ id: z.string(), type: z.string(), label: z.string().optional(), settings: z.record(z.string(), z.unknown()).optional(), input_bindings: z.record(z.string(), z.string()).optional(), position: z.union([NodePositionSchema, z.null()]).optional(), subworkflow: z.union([SubworkflowDefinitionSchema, z.null()]).optional() }).strict())
