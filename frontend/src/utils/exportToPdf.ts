// @ts-ignore
import jsPDF from 'jspdf'
import { ChatMessage } from '../api/models'

interface ExportToPdfOptions {
  filename?: string
  title?: string
  dateFormat?: Intl.DateTimeFormatOptions
  locale?: string
  logo?: string
  singlePage?: boolean
}

const defaultOptions: ExportToPdfOptions = {
  filename: 'conversation-export.pdf',
  title: 'Conversation AskMe', // Titre générique par défaut
  dateFormat: {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  },
  locale: 'fr-FR', // Format français par défaut
  singlePage: false
}

// Fonction pour détecter et remplacer les émojis
const processEmojis = (text: string): string => {
  // Détecteur d'emojis plus précis
  const emojiRegex =
    /[\u{1F300}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu

  // Remplacer les caractères spéciaux problématiques
  return (
    text
      // Remplacement des émojis courants avec des descriptions entre crochets
      .replace(/😊|😃|😄|🙂|☺️|😀/g, '[sourire]')
      .replace(/😂|🤣/g, '[rire]')
      .replace(/😉|😜|😝|🤪|😋/g, "[clin d'oeil]")
      .replace(/😍|🥰|❤️|💕|💓|💗|💖|💘|💝|💞|💟/g, '[coeur]')
      .replace(/🤔|🧐|🤨/g, '[réfléchit]')
      .replace(/👍|👎/g, '[pouce]')
      .replace(/👋|🖐️|✋|🤚/g, '[main]')
      .replace(/🎉|🎊|🎈|🎂|🎁/g, '[fête]')
      // Remplacer les autres émojis avec une description générique
      .replace(emojiRegex, '[emoji]')
      // Traiter les caractères spéciaux problématiques pour PDF
      .replace(/[\u2028\u2029]/g, '\n')
      .replace(/[\u0000-\u0008\u000B-\u000C\u000E-\u001F]/g, '')
      // Régler certains caractères spéciaux
      .replace(/Ø/g, 'O')
      .replace(/Þ/g, 'P')
      .replace(/€/g, 'EUR')
      .replace(/—/g, '-')
      .replace(/–/g, '-')
      .replace(/…/g, '...')
  )
}

// Fonction pour convertir le markdown basique en texte formaté
const parseMarkdown = (text: string): { text: string; format: Array<{ type: string; start: number; end: number }> } => {
  // Tableau pour stocker les formatages
  const formatElements: Array<{ type: string; start: number; end: number }> = []

  // Copie du texte pour manipulation
  let processedText = text

  // Remplacer des éléments de formatage markdown et enregistrer leurs positions

  // Gras (**texte**)
  let boldMatch
  const boldRegex = /\*\*(.*?)\*\*/g
  let boldOffset = 0

  while ((boldMatch = boldRegex.exec(text)) !== null) {
    const startPos = boldMatch.index - boldOffset
    const contentLength = boldMatch[1].length
    formatElements.push({
      type: 'bold',
      start: startPos,
      end: startPos + contentLength
    })

    // Remplacer **texte** par texte dans la chaîne traitée
    processedText = processedText.replace(boldMatch[0], boldMatch[1])
    boldOffset += 4 // Ajuster l'offset pour les prochaines correspondances (** au début et à la fin)
  }

  // Italique (*texte*)
  let italicMatch
  const italicRegex = /\*(.*?)\*/g
  let italicOffset = 0

  while ((italicMatch = italicRegex.exec(text)) !== null) {
    // S'assurer que ce n'est pas déjà détecté comme gras
    if (italicMatch[0].substring(0, 2) !== '**' && italicMatch[0].substring(italicMatch[0].length - 2) !== '**') {
      const startPos = italicMatch.index - italicOffset
      const contentLength = italicMatch[1].length
      formatElements.push({
        type: 'italic',
        start: startPos,
        end: startPos + contentLength
      })

      // Remplacer *texte* par texte dans la chaîne traitée
      processedText = processedText.replace(italicMatch[0], italicMatch[1])
      italicOffset += 2 // Ajuster l'offset (* au début et à la fin)
    }
  }

  // Retourner le texte nettoyé et les informations de formatage
  return {
    text: processedText,
    format: formatElements
  }
}

// Fonction pour formater une date selon la locale
const formatLocalizedDate = (dateString: string, locale: string, options: Intl.DateTimeFormatOptions): string => {
  const date = new Date(dateString)
  return date.toLocaleDateString(locale, options)
}

export const exportToPdf = async (messages: ChatMessage[], options: ExportToPdfOptions = {}): Promise<void> => {
  const mergedOptions = { ...defaultOptions, ...options }
  const { filename, title, dateFormat, locale, singlePage } = mergedOptions

  // Utiliser la locale fournie ou utiliser celle du navigateur
  const actualLocale = locale || navigator.language || 'fr-FR'

  // Calculer la hauteur approximative nécessaire pour tous les messages
  const estimateHeight = (messages: ChatMessage[]): number => {
    // Hauteur approximative pour l'en-tête et intro
    let totalHeight = 100

    // Estimation pour chaque message (très approximative)
    for (const message of messages) {
      if (typeof message.content === 'string') {
        // Hauteur moyenne par caractère (estimation grossière)
        const charCount = message.content.length
        // ~0.5mm par caractère avec ~60 caractères par ligne (300mm par 1000 caractères)
        // Ajout d'une marge de sécurité supplémentaire pour éviter les débordements
        totalHeight += Math.max(50, (charCount / 1000) * 350)
      } else {
        totalHeight += 50 // Hauteur par défaut pour les autres types
      }
    }

    return totalHeight
  }

  // Configuration du format de page
  let pdfFormat: any = 'a4'

  // Si l'option singlePage est activée, créer un PDF avec une seule page très grande
  if (singlePage) {
    const estimatedHeight = estimateHeight(messages)
    // Format personnalisé : largeur A4, hauteur calculée (minimum A4)
    pdfFormat = [210, Math.max(297, estimatedHeight)]
  }

  // Création du document PDF
  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: pdfFormat
  })

  // Paramètres du document
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = singlePage ? pdf.internal.pageSize.getHeight() : 297 // 297mm pour A4
  const margin = 20
  const contentWidth = pageWidth - 2 * margin
  let yPosition = margin + 10

  // En-tête élégant avec dégradé
  pdf.setFillColor(15, 108, 189) // Bleu primaire
  pdf.rect(0, 0, pageWidth, 30, 'F')

  // Ajout du titre personnalisé
  const docTitle: string = typeof title === 'string' ? title : 'Conversation AskMe'
  pdf.setTextColor(255, 255, 255)
  pdf.setFontSize(18)
  pdf.setFont('helvetica', 'bold')
  pdf.text(docTitle, margin, 20)

  // Ajout de la date d'export selon la locale
  const now = new Date()
  const exportDate = now.toLocaleDateString(actualLocale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
  const exportTime = now.toLocaleTimeString(actualLocale, {
    hour: '2-digit',
    minute: '2-digit'
  })

  pdf.setFontSize(10)
  pdf.setFont('helvetica', 'normal')
  pdf.setTextColor(240, 240, 240)

  // Texte localisé pour l'export
  let exportedOnText = 'Exported on'
  let atText = 'at'

  // Localisation du texte en fonction de la langue
  if (actualLocale.startsWith('fr')) {
    exportedOnText = 'Exporté le'
    atText = 'à'
  } else if (actualLocale.startsWith('es')) {
    exportedOnText = 'Exportado el'
    atText = 'a las'
  } else if (actualLocale.startsWith('de')) {
    exportedOnText = 'Exportiert am'
    atText = 'um'
  } else if (actualLocale.startsWith('it')) {
    exportedOnText = 'Esportato il'
    atText = 'alle'
  }

  const dateText = `${exportedOnText}: ${exportDate} ${atText} ${exportTime}`
  const dateWidth = (pdf.getStringUnitWidth(dateText) * 10) / pdf.internal.scaleFactor
  pdf.text(dateText, pageWidth - margin - dateWidth, 20)

  yPosition = 50 // Commencer le contenu en dessous de l'en-tête

  // Fonction pour ajouter les numéros de page
  const addPageNumber = () => {
    // Utiliser le nombre de pages du document
    const totalPages = pdf.internal.pages.length - 1 // -1 car les pages commencent à l'index 1
    for (let i = 1; i <= totalPages; i++) {
      pdf.setPage(i)
      pdf.setFontSize(9)
      pdf.setTextColor(150, 150, 150)
      pdf.text(`Page ${i} sur ${totalPages}`, pageWidth - 35, pageHeight - 10)
    }
  }

  // Introduction de la conversation (localisée)
  pdf.setFontSize(11)
  pdf.setTextColor(100, 100, 100)
  pdf.setFont('helvetica', 'italic')

  // Texte localisé pour l'introduction
  let introText = 'This conversation contains exchanges with the assistant.'

  // Localisation du texte d'introduction
  if (actualLocale.startsWith('fr')) {
    introText = "Cette conversation contient l'échange avec AskMe."
  } else if (actualLocale.startsWith('es')) {
    introText = 'Esta conversación contiene intercambios con AskMe.'
  } else if (actualLocale.startsWith('de')) {
    introText = 'Dieses Gespräch enthält den Austausch mit AskMe.'
  } else if (actualLocale.startsWith('it')) {
    introText = 'Questa conversazione contiene scambi con AskMe.'
  }

  pdf.text(introText, margin, yPosition)
  yPosition += 8

  // Ligne de séparation
  pdf.setDrawColor(200, 200, 200)
  pdf.setLineWidth(0.5)
  pdf.line(margin, yPosition, pageWidth - margin, yPosition)
  yPosition += 12

  // Fonction pour couper une bulle trop grande sur plusieurs pages
  const splitBubbleAcrossPages = (
    lines: string[],
    textX: number,
    textY: number,
    lineHeight: number,
    bubbleX: number,
    bubbleWidth: number,
    bubblePadding: number,
    isUser: boolean,
    radius: number
  ) => {
    // Nombre de lignes par page (approximatif)
    const linesPerPage = Math.floor((pageHeight - margin - textY) / lineHeight)

    if (linesPerPage <= 0) {
      // Pas assez d'espace, créer une nouvelle page
      pdf.addPage()
      return createMessageBubble(lines.join('\n'), margin + 15, isUser)
    }

    // Premier groupe de lignes (sur la page actuelle)
    const firstPageLines = lines.slice(0, linesPerPage)
    // Lignes restantes (pour la page suivante)
    const nextPageLines = lines.slice(linesPerPage)

    // Calculer la hauteur de la bulle pour la première page
    const firstPageTextHeight = firstPageLines.length * lineHeight
    const firstPageBubbleHeight = firstPageTextHeight + 2 * bubblePadding

    // Dessiner la première partie de la bulle
    if (isUser) {
      pdf.setFillColor(237, 245, 253)
      pdf.setDrawColor(220, 230, 240)
    } else {
      pdf.setFillColor(255, 255, 255)
      pdf.setDrawColor(230, 230, 230)
    }

    // Augmenter le radius pour des coins plus arrondis
    const bubbleRadius = 5

    // Bulle principale (première page) avec padding supplémentaire
    pdf.roundedRect(
      bubbleX,
      textY - bubblePadding,
      bubbleWidth,
      firstPageBubbleHeight + 10,
      bubbleRadius,
      bubbleRadius,
      'FD'
    )

    // Dessiner le texte pour la première page
    pdf.setFont('helvetica', 'normal')
    pdf.setTextColor(50, 50, 50)

    for (let i = 0; i < firstPageLines.length; i++) {
      const currentY = textY + i * lineHeight
      pdf.text(firstPageLines[i] || '', textX, currentY)
    }

    // Créer une nouvelle page pour la suite
    pdf.addPage()
    const newY = margin + 15

    // Position pour le texte sur la nouvelle page avec padding adéquat
    const newTextY = newY + bubblePadding

    // Dessiner la deuxième partie de la bulle
    if (isUser) {
      pdf.setFillColor(237, 245, 253)
      pdf.setDrawColor(220, 230, 240)
    } else {
      pdf.setFillColor(255, 255, 255)
      pdf.setDrawColor(230, 230, 230)
    }

    // Calculer la hauteur pour les lignes restantes
    const remainingTextHeight = nextPageLines.length * lineHeight
    const remainingBubbleHeight = remainingTextHeight + 2 * bubblePadding

    // Bulle principale (deuxième page) avec padding supplémentaire
    pdf.roundedRect(bubbleX, newY, bubbleWidth, remainingBubbleHeight + 10, bubbleRadius, bubbleRadius, 'FD')

    // Dessiner le texte pour la deuxième page
    for (let i = 0; i < nextPageLines.length; i++) {
      const currentY = newTextY + i * lineHeight
      pdf.text(nextPageLines[i] || '', textX, currentY)
    }

    // Retourner la nouvelle position Y
    return newY + remainingBubbleHeight + 5
  }

  // Création d'une bulle de conversation avec style
  const createMessageBubble = (text: string, y: number, isUser: boolean): number => {
    // Nettoyage du texte: suppression des marqueurs de citation et traitement des émojis
    let cleanText = text.replace(/\^\d+\^/g, '')

    // Traitement spécifique des émojis et caractères spéciaux
    cleanText = processEmojis(cleanText)

    // Traiter les blocs de code en premier
    cleanText = cleanText.replace(/```([^`]+)```/g, (match, codeBlock) => {
      return '\n---\n' + codeBlock.trim() + '\n---\n'
    })

    // Parser le markdown pour obtenir le texte et les formats
    const { text: parsedText, format } = parseMarkdown(cleanText)
    cleanText = parsedText

    // Ajout d'un espace au début pour éviter le problème de première ligne
    if (!cleanText.startsWith(' ') && !cleanText.startsWith('\n')) {
      cleanText = ' ' + cleanText
    }

    // Paramètres de la bulle
    const fontSize = 10
    pdf.setFontSize(fontSize)

    // Calcul de la largeur maximum du message (75% de la largeur disponible - augmenté pour plus d'espace)
    const maxWidth = contentWidth * 0.75

    // Dimensions de la bulle avec padding important
    const bubblePadding = 15 // Padding général important

    // Découpage du texte pour l'adapter à la largeur avec traitement des sauts de ligne
    cleanText = cleanText.replace(/\\n/g, '\n')

    // Calcul de la hauteur du texte
    const lineHeight = fontSize * 0.35 * 1.6 // Espacement des lignes

    // Marge supplémentaire pour le texte (padding interne)
    const textPadding = 10 // Augmenté pour plus d'espace autour du texte

    // Réduire la largeur disponible pour le texte tout en laissant plus d'espace
    const adjustedMaxWidth = maxWidth - textPadding * 2

    // Diviser le texte en lignes avec la largeur ajustée
    const lines = pdf.splitTextToSize(cleanText, adjustedMaxWidth)

    const textHeight = lines.length * lineHeight

    // Hauteur totale de la bulle
    const bubbleHeight = textHeight + bubblePadding * 2

    // Calcul de la largeur réelle nécessaire pour chaque ligne
    let maxLineWidth = 0
    if (lines && lines.length > 0) {
      for (let i = 0; i < lines.length; i++) {
        // Mesurer la largeur exacte de la ligne
        const lineWidth = (pdf.getStringUnitWidth(lines[i]) * fontSize) / pdf.internal.scaleFactor
        if (lineWidth > maxLineWidth) {
          maxLineWidth = lineWidth
        }
      }
    }

    // Ajouter un padding significatif à la largeur calculée
    const contentBubbleWidth = maxLineWidth + textPadding * 2

    // S'assurer d'une largeur minimale plus grande et d'une largeur maximale étendue
    const minBubbleWidth = Math.max(maxWidth * 0.3, 70) // Largeur minimale plus grande
    const bubbleWidth = Math.min(maxWidth, Math.max(contentBubbleWidth, minBubbleWidth))

    // Position X de la bulle selon l'expéditeur, ajustée pour les bulles plus larges
    const bubbleX = isUser ? pageWidth - margin - bubbleWidth : margin

    // Vérification s'il faut gérer les sauts de page
    // En mode page unique, on ne fait pas de vérification
    if (!singlePage && y + bubbleHeight + 10 > pageHeight - margin) {
      // La bulle est trop grande pour tenir sur cette page
      if (bubbleHeight < pageHeight - 2 * margin) {
        pdf.addPage()
        y = margin + 15 // Position Y sur la nouvelle page
      } else {
        // Pour les très grandes bulles, les diviser sur plusieurs pages
        const textX = bubbleX + textPadding
        const textY = y + bubblePadding
        return splitBubbleAcrossPages(lines, textX, textY, lineHeight, bubbleX, bubbleWidth, bubblePadding, isUser, 4)
      }
    }

    // Style de la bulle selon l'expéditeur
    if (isUser) {
      // Bulle utilisateur (bleu clair)
      pdf.setFillColor(237, 245, 253) // #EDF5FD
      pdf.setDrawColor(220, 230, 240)
    } else {
      // Bulle assistant (blanc avec bordure légère)
      pdf.setFillColor(255, 255, 255)
      pdf.setDrawColor(230, 230, 230)
    }

    // Dessin de la bulle arrondie avec ombre légère
    const radius = 5 // Augmenté pour une esthétique plus moderne

    // Ombre légère (optionnel)
    pdf.setDrawColor(240, 240, 240)
    pdf.setFillColor(240, 240, 240)
    pdf.roundedRect(bubbleX + 1, y + 1, bubbleWidth, bubbleHeight, radius, radius, 'F')

    // Bulle principale
    if (isUser) {
      pdf.setFillColor(237, 245, 253)
      pdf.setDrawColor(220, 230, 240)
    } else {
      pdf.setFillColor(255, 255, 255)
      pdf.setDrawColor(230, 230, 230)
    }
    pdf.roundedRect(bubbleX, y, bubbleWidth, bubbleHeight, radius, radius, 'FD')

    // Positionnement du texte dans la bulle avec un décalage suffisant pour éviter les bords
    const textX = bubbleX + textPadding
    const textY = y + bubblePadding

    // Ajout du texte ligne par ligne
    if (lines && lines.length > 0) {
      for (let i = 0; i < lines.length; i++) {
        const currentY = textY + i * lineHeight
        pdf.setFont('helvetica', 'normal')
        pdf.setTextColor(50, 50, 50)
        pdf.text(lines[i] || '', textX, currentY)
      }
    }

    // Retourner la nouvelle position Y
    return y + bubbleHeight + 5
  }

  // Traitement de chaque message
  for (let i = 0; i < messages.length; i++) {
    const message = messages[i]

    // Ignorer les messages qui ne sont pas des chaînes ou qui sont des messages d'outil
    if (typeof message.content !== 'string' || message.role === 'tool' || message.role === 'error') {
      continue
    }

    const isUser = message.role === 'user'
    const sender = isUser ? 'Vous' : 'Assistant'

    // Vérifier si nous devons créer une nouvelle page
    if (!singlePage && yPosition > pageHeight - 50) {
      pdf.addPage()
      yPosition = margin + 15
    }

    // Affichage de l'expéditeur et de l'horodatage selon la locale
    if (message.date) {
      const messageDate = new Date(message.date)
      const messageTime = messageDate.toLocaleTimeString(actualLocale, {
        hour: '2-digit',
        minute: '2-digit'
      })

      // Texte localisé pour l'expéditeur
      let userText = 'You'
      let assistantText = 'Assistant'

      // Localisation du texte d'expéditeur
      if (actualLocale.startsWith('fr')) {
        userText = 'Vous'
        assistantText = 'Assistant'
      } else if (actualLocale.startsWith('es')) {
        userText = 'Usted'
        assistantText = 'Asistente'
      } else if (actualLocale.startsWith('de')) {
        userText = 'Sie'
        assistantText = 'Assistent'
      } else if (actualLocale.startsWith('it')) {
        userText = 'Tu'
        assistantText = 'Assistente'
      }

      // Sélection du bon texte en fonction du rôle
      const sender = isUser ? userText : assistantText

      pdf.setFontSize(9)
      pdf.setFont('helvetica', 'bold')

      if (isUser) {
        // Aligné à droite pour l'utilisateur
        pdf.setTextColor(15, 108, 189)
        const infoText = `${sender} - ${messageTime}`
        const textWidth = (pdf.getStringUnitWidth(infoText) * 9) / pdf.internal.scaleFactor
        pdf.text(infoText, pageWidth - margin - textWidth, yPosition - 2)
      } else {
        // Aligné à gauche pour l'assistant
        pdf.setTextColor(100, 100, 100)
        pdf.text(`${sender} - ${messageTime}`, margin, yPosition - 2)
      }
    }

    // Création de la bulle de message
    yPosition = createMessageBubble(message.content, yPosition, isUser)

    // Espace entre les messages
    yPosition += 10
  }

  // Pied de page - uniquement ajouté à la dernière page en mode une seule page
  pdf.setDrawColor(200, 200, 200)
  pdf.setLineWidth(0.5)

  const footerY = singlePage ? Math.min(yPosition + 10, pdf.internal.pageSize.getHeight() - 18) : pageHeight - 18

  pdf.line(margin, footerY, pageWidth - margin, footerY)

  pdf.setFontSize(8)
  pdf.setTextColor(120, 120, 120)
  pdf.setFont('helvetica', 'italic')

  // Texte localisé pour le pied de page
  let footerText = 'Document exported from the conversation application'

  // Localisation du texte de pied de page
  if (actualLocale.startsWith('fr')) {
    footerText = "Document exporté depuis l'application de conversation"
  } else if (actualLocale.startsWith('es')) {
    footerText = 'Documento exportado desde la aplicación de conversación'
  } else if (actualLocale.startsWith('de')) {
    footerText = 'Dokument aus der Konversationsanwendung exportiert'
  } else if (actualLocale.startsWith('it')) {
    footerText = "Documento esportato dall'applicazione di conversazione"
  }

  pdf.text(footerText, margin, footerY + 6)

  // Ajout des numéros de page (uniquement si plusieurs pages)
  if (!singlePage) {
    // Mise à jour de la fonction pour prendre en compte la locale
    const addLocalizedPageNumber = () => {
      // Utiliser le nombre de pages du document
      const totalPages = pdf.internal.pages.length - 1 // -1 car les pages commencent à l'index 1

      // Texte localisé pour les pages
      let pageText = 'Page'
      let ofText = 'of'

      // Localisation du texte pour les numéros de page
      if (actualLocale.startsWith('fr')) {
        pageText = 'Page'
        ofText = 'sur'
      } else if (actualLocale.startsWith('es')) {
        pageText = 'Página'
        ofText = 'de'
      } else if (actualLocale.startsWith('de')) {
        pageText = 'Seite'
        ofText = 'von'
      } else if (actualLocale.startsWith('it')) {
        pageText = 'Pagina'
        ofText = 'di'
      }

      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i)
        pdf.setFontSize(9)
        pdf.setTextColor(150, 150, 150)
        pdf.text(`${pageText} ${i} ${ofText} ${totalPages}`, pageWidth - 40, pageHeight - 10)
      }
    }

    addLocalizedPageNumber()
  }

  // Enregistrement du PDF
  pdf.save(filename)
}
