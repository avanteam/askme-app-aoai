import { cloneDeep } from 'lodash'

import { AskResponse, Citation } from '../../api'

export type ParsedAnswer = {
  citations: Citation[]
  markdownFormatText: string,
  generated_chart: string | null
} | null

export const enumerateCitations = (citations: Citation[]) => {
  const filepathMap = new Map()
  for (const citation of citations) {
    const { filepath } = citation
    let part_i = 1
    if (filepathMap.has(filepath)) {
      part_i = filepathMap.get(filepath) + 1
    }
    filepathMap.set(filepath, part_i)
    citation.part_index = part_i
  }
  return citations
}

export function parseAnswer(answer: AskResponse): ParsedAnswer {
  if (typeof answer.answer !== "string") return null
  let answerText = answer.answer
  const citationLinks = answerText.match(/\[(doc\d\d?\d?)]/g)

  const lengthDocN = '[doc'.length

  let filteredCitations = [] as Citation[]
  let citationReindex = 0
  citationLinks?.forEach(link => {
    // Replacing the links/citations with number
    const citationIndex = link.slice(lengthDocN, link.length - 1)
    const citation = cloneDeep(answer.citations[Number(citationIndex) - 1]) as Citation
    if (!filteredCitations.find(c => c.id === citationIndex) && citation) {
      answerText = answerText.replaceAll(link, ` ^${++citationReindex}^ `)
      citation.id = citationIndex // original doc index to de-dupe
      citation.reindex_id = citationReindex.toString() // reindex from 1 for display
      filteredCitations.push(citation)
    }
  })

  filteredCitations = enumerateCitations(filteredCitations)

  /* Remplacement des liens pour ouvrir les documents */
  const matchesIdDocs = answerText.matchAll(/\[iddoc\|([^|]+)\|([^|]+)\]/g);

  for (const matchIdDoc of matchesIdDocs) {
      const idDuDoc = matchIdDoc[1]; // Premier groupe capturé (ID_DU_DOC)
      const refDuDoc = matchIdDoc[2]; // Deuxième groupe capturé (REF_DU_DOC)

      // Action personnalisée
      answerText = answerText.replaceAll(
          `[iddoc|${idDuDoc}|${refDuDoc}]`,
          `[${refDuDoc}](${idDuDoc})`
      );
  }

  return {
    citations: filteredCitations,
    markdownFormatText: answerText,
    generated_chart: answer.generated_chart
  }
}
