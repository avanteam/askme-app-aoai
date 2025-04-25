import React, { useContext, useEffect, useState, useRef } from 'react'
import {
  Icon,
  Stack,
  Text
} from '@fluentui/react'
import { AppStateContext } from '../../state/AppProvider'

import styles from './HelpPanel.module.css'

import LocalizedStrings from 'react-localization';

interface HelpPanelProps {}

export function HelpPanel(_props: HelpPanelProps) {
  const appStateContext = useContext(AppStateContext)
  const [isVisible, setIsVisible] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  
  // Fermeture du panneau d'aide
  const handleCloseHelp = () => {
    setIsVisible(false)
    // Délai avant de réellement masquer le panneau (pour permettre l'animation)
    setTimeout(() => {
      appStateContext?.dispatch({ type: 'TOGGLE_HELP_PANEL' })
    }, 300)
  }
  
  // Gestion du clic sur l'overlay (fond semi-transparent)
  const handleOverlayClick = (e: React.MouseEvent) => {
    // S'assurer que le clic était bien sur l'overlay et pas sur le panneau
    if (e.target === e.currentTarget) {
      handleCloseHelp()
    }
  }
  
  // Fonction pour copier un exemple de prompt dans le presse-papiers
  const copyPromptExample = (text: string) => {
    navigator.clipboard.writeText(text)
      .then(() => {
        // Optionnellement, afficher une notification de succès
        console.log('Exemple copié dans le presse-papiers')
      })
      .catch(err => {
        console.error('Erreur lors de la copie: ', err)
      })
  }

  useEffect(() => {
    // Définir l'animation d'apparition après montage du composant
    setTimeout(() => {
      setIsVisible(true)
    }, 50)
    
    localizedStrings.setLanguage((appStateContext?.state.userLanguage) ? appStateContext?.state.userLanguage : 'FR');
    
    // Ajouter l'écouteur pour la touche Escape
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseHelp()
      }
    }
    
    document.addEventListener('keydown', handleEscapeKey)
    
    // Nettoyage lors du démontage
    return () => {
      document.removeEventListener('keydown', handleEscapeKey)
    }
  }, [appStateContext?.state.userLanguage])

  return (
    <>
      {/* Overlay semi-transparent */}
      <div 
        className={`${styles.overlay} ${isVisible ? styles.overlayVisible : ''}`}
        onClick={handleOverlayClick}
        aria-hidden="true"
      />
      
      {/* Panneau d'aide */}
      <div 
        ref={panelRef}
        className={`${styles.container} ${isVisible ? styles.visible : ''}`} 
        aria-label="panneau d'aide"
      >
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>{localizedStrings.helpPanelTitle}</h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label={localizedStrings.hide}
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        
        <div className={styles.helpContent}>
          {/* Section d'introduction */}
          <div className={styles.helpSection}>
            <h3 className={styles.sectionTitle}>{localizedStrings.introTitle}</h3>
            <div className={styles.sectionContent}>
              {localizedStrings.introContent}
            </div>
          </div>
          
          {/* Section des exemples de prompts */}
          <div className={styles.helpSection}>
            <h3 className={styles.sectionTitle}>{localizedStrings.promptExamplesTitle}</h3>
            <div className={styles.sectionContent}>
              <p>{localizedStrings.promptExamplesIntro}</p>
              
              {/* Exemples de prompts */}
              <div 
                className={styles.promptExample}
                onClick={() => copyPromptExample(localizedStrings.promptExample1)}
                title={localizedStrings.clickToCopy}
              >
                {localizedStrings.promptExample1}
              </div>
              
              <div 
                className={styles.promptExample}
                onClick={() => copyPromptExample(localizedStrings.promptExample2)}
                title={localizedStrings.clickToCopy}
              >
                {localizedStrings.promptExample2}
              </div>
              
              <div 
                className={styles.promptExample}
                onClick={() => copyPromptExample(localizedStrings.promptExample3)}
                title={localizedStrings.clickToCopy}
              >
                {localizedStrings.promptExample3}
              </div>
            </div>
          </div>
          
          {/* Section des conseils d'utilisation */}
          <div className={styles.helpSection}>
            <h3 className={styles.sectionTitle}>{localizedStrings.tipsTitle}</h3>
            <div className={styles.sectionContent}>
              <p>{localizedStrings.tipsContent}</p>
              <ul>
                <li>{localizedStrings.tip1}</li>
                <li>{localizedStrings.tip2}</li>
                <li>{localizedStrings.tip3}</li>
                <li>{localizedStrings.tip4}</li>
                <li>{localizedStrings.tip5}</li>
              </ul>
            </div>
          </div>
          
          {/* Section des limitations */}
          <div className={styles.helpSection}>
            <h3 className={styles.sectionTitle}>{localizedStrings.limitationsTitle}</h3>
            <div className={styles.sectionContent}>
              <p>{localizedStrings.limitationsContent}</p>
              <ul>
                <li>{localizedStrings.limitation1}</li>
                <li>{localizedStrings.limitation2}</li>
                <li>{localizedStrings.limitation3}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

let localizedStrings = new LocalizedStrings({
  FR: {
    helpPanelTitle: 'Guide d\'utilisation de l\'assistant',
    hide: 'Fermer',
    clickToCopy: 'Cliquer pour copier cet exemple',
    
    // Section d'introduction
    introTitle: 'Bienvenue dans l\'aide de l\'assistant',
    introContent: 'Cet assistant utilise l\'intelligence artificielle pour vous aider à trouver des informations pertinentes dans vos documents. Voici quelques conseils pour tirer le meilleur parti de votre expérience.',
    
    // Section des exemples de prompts
    promptExamplesTitle: 'Exemples de questions efficaces',
    promptExamplesIntro: 'Cliquez sur un exemple pour le copier dans votre presse-papiers :',
    promptExample1: 'Quelles sont les principales fonctionnalités du produit X ?',
    promptExample2: 'Résume les points clés du document sur la stratégie commerciale 2025.',
    promptExample3: 'Compare les avantages et inconvénients des options A et B mentionnées dans le rapport.',
    
    // Section des conseils
    tipsTitle: 'Conseils pour de meilleurs résultats',
    tipsContent: 'Pour obtenir les réponses les plus précises et pertinentes :',
    tip1: 'Soyez spécifique dans vos questions.',
    tip2: 'Incluez des mots-clés pertinents qui se trouvent dans vos documents.',
    tip3: 'Pour des analyses complexes, décomposez votre demande en plusieurs questions plus simples.',
    tip4: 'Si la réponse n\'est pas satisfaisante, essayez de reformuler votre question.',
    tip5: 'Utilisez les sources citées pour vérifier les informations fournies.',
    
    // Section des limitations
    limitationsTitle: 'Limitations à connaître',
    limitationsContent: 'L\'assistant a certaines limitations :',
    limitation1: 'Il ne peut accéder qu\'aux documents qui ont été indexés dans la base de connaissances.',
    limitation2: 'Il peut parfois mal interpréter certaines demandes complexes ou ambiguës.',
    limitation3: 'L\'assistant n\'a pas connaissance des événements ou informations postérieurs à sa dernière mise à jour.'
  },
  EN: {
    helpPanelTitle: 'Assistant User Guide',
    hide: 'Close',
    clickToCopy: 'Click to copy this example',
    
    // Introduction section
    introTitle: 'Welcome to the Assistant Help',
    introContent: 'This assistant uses artificial intelligence to help you find relevant information from your documents. Here are some tips to make the most of your experience.',
    
    // Prompt examples section
    promptExamplesTitle: 'Examples of Effective Questions',
    promptExamplesIntro: 'Click on an example to copy it to your clipboard:',
    promptExample1: 'What are the main features of product X?',
    promptExample2: 'Summarize the key points from the 2025 business strategy document.',
    promptExample3: 'Compare the advantages and disadvantages of options A and B mentioned in the report.',
    
    // Tips section
    tipsTitle: 'Tips for Better Results',
    tipsContent: 'To get the most accurate and relevant answers:',
    tip1: 'Be specific in your questions.',
    tip2: 'Include relevant keywords that are found in your documents.',
    tip3: 'For complex analyses, break down your request into multiple simpler questions.',
    tip4: 'If the answer is not satisfactory, try rephrasing your question.',
    tip5: 'Use the cited sources to verify the information provided.',
    
    // Limitations section
    limitationsTitle: 'Limitations to Be Aware Of',
    limitationsContent: 'The assistant has certain limitations:',
    limitation1: 'It can only access documents that have been indexed in the knowledge base.',
    limitation2: 'It may sometimes misinterpret certain complex or ambiguous requests.',
    limitation3: 'The assistant is not aware of events or information after its last update.'
  },
});