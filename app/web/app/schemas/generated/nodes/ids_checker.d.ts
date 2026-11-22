/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Validates the IFC model against one or more IDS specifications.
 */
export interface IdsCheckerNodeSchema {
  settings: {
    /**
     * Path to the IDS specification file to validate against.
     */
    ids_file?: string
    /**
     * Wenn aktiviert, werden die Ergebnisse zusätzlich nach Specification gruppiert ausgegeben (für Report-Generierung). Die kombinierten Listen (failed_express_ids, passed_express_ids) werden immer erstellt.
     */
    generate_detailed_report?: boolean
    /**
     * Format für den generierten Report. Nur wirksam wenn generate_detailed_report aktiviert ist.
     */
    report_format?: (('json' | 'html' | 'bcf') | null)
  }
  result: {
    /**
     * Qualified references of entities that failed at least one IDS requirement (combined across all specifications).
     */
    failed_express_ids?: string[]
    /**
     * Qualified references of entities that passed all applicable IDS requirements (combined across all specifications).
     */
    passed_express_ids?: string[]
    /**
     * Per-specification breakdown. Only included when generate_detailed_report is enabled.
     */
    specifications?: ({
      /**
       * Name of the IDS specification.
       */
      name?: string
      /**
       * Qualified references of entities that failed this specification's requirements.
       */
      failed_express_ids?: string[]
      /**
       * Qualified references of entities that passed this specification's requirements.
       */
      passed_express_ids?: string[]
    }[] | null)
    /**
     * Path to the generated report file. Only included when generate_detailed_report and report_format are enabled.
     */
    report_path?: (string | null)
  }
  inputs: {
    /**
     * Qualified element references (`<slug>:expr:<id>`) to validate against the IDS requirements. Mixed-model lists are grouped by model and each model is validated once. Bind ifc_element_filter output here.
     */
    express_ids: string[]
  }
}
