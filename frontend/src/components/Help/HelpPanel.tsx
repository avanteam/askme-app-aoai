import React, { useContext, useEffect, useState, useRef } from 'react'
import {
  Icon,
  Text,
  MessageBar,
  MessageBarType,
  SearchBox,
  Pivot,
  PivotItem,
  FocusZone,
  List
} from '@fluentui/react'
import { AppStateContext } from '../../state/AppProvider'

import styles from './HelpPanel.module.css'

import LocalizedStrings from 'react-localization';

// Définition des types pour les prompts prédéfinis
interface PromptTranslation {
  FR: string;
  EN: string;
  [key: string]: string; // Permet l'indexation avec une chaîne
}

interface PredefinedPrompt {
  id: number;
  category: string;
  title: PromptTranslation;
  description: PromptTranslation;
  prompt: PromptTranslation;
}

// Liste des prompts prédéfinis
const predefinedPrompts: PredefinedPrompt[] = [
  // Catégorie Général
  {
    id: 1,
    category: 'general',
    title: {
      FR: 'Trouver des informations sur un sujet',
      EN: 'Find information on a topic'
    },
    description: {
      FR: 'Recherche d\'informations générales sur un sujet précis',
      EN: 'Search for general information on a specific topic'
    },
    prompt: {
      FR: 'Quelles informations avons-nous sur [sujet spécifique] ? Présente un résumé des points clés.',
      EN: 'What information do we have about [specific topic]? Present a summary of key points.'
    }
  },
  {
    id: 2,
    category: 'general',
    title: {
      FR: 'Dernières mises à jour',
      EN: 'Latest updates'
    },
    description: {
      FR: 'Recherche des informations récentes sur un sujet',
      EN: 'Search for recent information on a topic'
    },
    prompt: {
      FR: 'Quelles sont les dernières informations ou mises à jour concernant [sujet] ? Y a-t-il eu des changements récents ?',
      EN: 'What are the latest information or updates regarding [topic]? Have there been any recent changes?'
    }
  },
  // Catégorie Documents
  {
    id: 3,
    category: 'documents',
    title: {
      FR: 'Résumé de document',
      EN: 'Document summary'
    },
    description: {
      FR: 'Obtenir un résumé concis d\'un document spécifique',
      EN: 'Get a concise summary of a specific document'
    },
    prompt: {
      FR: 'Peux-tu me faire un résumé du document concernant [sujet ou nom du document] ? Inclus les points principaux et les conclusions.',
      EN: 'Can you summarize the document about [topic or document name]? Include the main points and conclusions.'
    }
  },
  {
    id: 4,
    category: 'documents',
    title: {
      FR: 'Recherche de procédure',
      EN: 'Procedure search'
    },
    description: {
      FR: 'Trouver une procédure ou un processus spécifique',
      EN: 'Find a specific procedure or process'
    },
    prompt: {
      FR: 'Quelle est la procédure pour [action spécifique] ? Peux-tu me donner les étapes à suivre ?',
      EN: 'What is the procedure for [specific action]? Can you give me the steps to follow?'
    }
  },
  // Catégorie Analyse
  {
    id: 5,
    category: 'analysis',
    title: {
      FR: 'Comparaison d\'informations',
      EN: 'Information comparison'
    },
    description: {
      FR: 'Comparer différentes informations ou approches',
      EN: 'Compare different information or approaches'
    },
    prompt: {
      FR: 'Peux-tu comparer les différentes approches concernant [sujet] ? Quels sont les avantages et inconvénients de chaque méthode ?',
      EN: 'Can you compare the different approaches regarding [topic]? What are the advantages and disadvantages of each method?'
    }
  },
  {
    id: 6,
    category: 'analysis',
    title: {
      FR: 'Analyse des tendances',
      EN: 'Trend analysis'
    },
    description: {
      FR: 'Analyser les tendances sur un sujet spécifique',
      EN: 'Analyze trends on a specific topic'
    },
    prompt: {
      FR: 'Quelles sont les tendances principales concernant [sujet] dans nos documents ? Y a-t-il une évolution notable ?',
      EN: 'What are the main trends regarding [topic] in our documents? Is there a notable evolution?'
    }
  },
  // Catégorie Rédaction
  {
    id: 7,
    category: 'writing',
    title: {
      FR: 'Rédaction d\'un message',
      EN: 'Draft a message'
    },
    description: {
      FR: 'Aide à la rédaction d\'un message professionnel',
      EN: 'Help drafting a professional message'
    },
    prompt: {
      FR: 'Aide-moi à rédiger un message professionnel pour [contexte] qui inclut les informations suivantes : [points clés]. Le ton doit être [formel/informel].',
      EN: 'Help me draft a professional message for [context] that includes the following information: [key points]. The tone should be [formal/informal].'
    }
  },
  {
    id: 8,
    category: 'writing',
    title: {
      FR: 'Simplification d\'un texte',
      EN: 'Text simplification'
    },
    description: {
      FR: 'Simplifier un texte technique ou complexe',
      EN: 'Simplify a technical or complex text'
    },
    prompt: {
      FR: 'Peux-tu m\'aider à simplifier cette information technique : [texte complexe] ? Je voudrais l\'expliquer à quelqu\'un qui n\'est pas spécialiste du domaine.',
      EN: 'Can you help me simplify this technical information: [complex text]? I would like to explain it to someone who is not a specialist in the field.'
    }
  }
];

interface CategoryTranslation {
  FR: string;
  EN: string;
  [key: string]: string; // Permet l'indexation avec une chaîne
}

// Définition des catégories pour l'organisation des prompts
const categories = [
  { key: 'general', name: { FR: 'Général', EN: 'General' } as CategoryTranslation, icon: 'Info' },
  { key: 'documents', name: { FR: 'Documents', EN: 'Documents' } as CategoryTranslation, icon: 'Document' },
  { key: 'analysis', name: { FR: 'Analyse', EN: 'Analysis' } as CategoryTranslation, icon: 'AnalyticsReport' },
  { key: 'writing', name: { FR: 'Rédaction', EN: 'Writing' } as CategoryTranslation, icon: 'Edit' }
];

interface HelpPanelProps {}

export function HelpPanel(_props: HelpPanelProps) {
  const appStateContext = useContext(AppStateContext)
  const [isVisible, setIsVisible] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [filteredPrompts, setFilteredPrompts] = useState<PredefinedPrompt[]>(predefinedPrompts)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [currentLanguage, setCurrentLanguage] = useState('FR')
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
        // Afficher la notification toast
        setToastMessage(localizedStrings.promptCopied)
        setShowToast(true)
        
        // Masquer après 3 secondes
        setTimeout(() => {
          setShowToast(false)
        }, 3000)
      })
      .catch(err => {
        console.error('Erreur lors de la copie: ', err)
        // Notification d'erreur
        setToastMessage(localizedStrings.copyError)
        setShowToast(true)
        setTimeout(() => {
          setShowToast(false)
        }, 3000)
      })
  }

  // Fonction pour filtrer les prompts en fonction de la recherche et de la catégorie
  const filterPrompts = () => {
    let filtered = predefinedPrompts;
    
    // Filtrer par catégorie si une catégorie est sélectionnée
    if (selectedCategory) {
      filtered = filtered.filter(prompt => prompt.category === selectedCategory);
    }
    
    // Filtrer par recherche si une recherche est effectuée
    if (searchQuery.trim() !== '') {
      const lowerCaseQuery = searchQuery.toLowerCase();
      filtered = filtered.filter(prompt => {
        const title = prompt.title[currentLanguage].toLowerCase();
        const description = prompt.description[currentLanguage].toLowerCase();
        const promptText = prompt.prompt[currentLanguage].toLowerCase();
        
        return (
          title.includes(lowerCaseQuery) || 
          description.includes(lowerCaseQuery) || 
          promptText.includes(lowerCaseQuery)
        );
      });
    }
    
    setFilteredPrompts(filtered);
  }

  // Mettre à jour les filtres lorsque la recherche ou la catégorie change
  useEffect(() => {
    filterPrompts();
  }, [searchQuery, selectedCategory, currentLanguage]);

  useEffect(() => {
    // Définir l'animation d'apparition après montage du composant
    setTimeout(() => {
      setIsVisible(true)
    }, 50)
    
    // Déterminer la langue en fonction du contexte de l'application
    const userLang = appStateContext?.state.userLanguage || 'FR';
    setCurrentLanguage(userLang);
    
    localizedStrings.setLanguage(userLang);
    
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

  // Rendu d'un élément de prompt
  const renderPromptItem = (item?: PredefinedPrompt) => {
    if (!item) return null;
    
    const getCategoryIcon = (categoryKey: string) => {
      const category = categories.find(cat => cat.key === categoryKey);
      return category ? category.icon : 'Tag';
    };
    
    const getCategoryName = (categoryKey: string) => {
      const category = categories.find(cat => cat.key === categoryKey);
      return category ? category.name[currentLanguage] : categoryKey;
    };
    
    return (
      <div className={styles.promptCard} onClick={() => copyPromptExample(item.prompt[currentLanguage])}>
        <div className={styles.promptCardHeader}>
          <Icon iconName={getCategoryIcon(item.category)} className={styles.promptCardIcon} />
          <div className={styles.promptCardTitle}>{item.title[currentLanguage]}</div>
        </div>
        <div className={styles.promptCardDescription}>{item.description[currentLanguage]}</div>
        <div className={styles.promptCardPrompt}>
          <div className={styles.promptLabel}>{localizedStrings.promptLabel}</div>
          <div className={styles.promptText}>
            <Icon iconName="Copy" className={styles.copyIcon} />
            {item.prompt[currentLanguage]}
          </div>
        </div>
        <div className={styles.promptCardCategory}>
          <Icon iconName="Tag" className={styles.promptCardCategoryIcon} />
          {getCategoryName(item.category)}
        </div>
      </div>
    );
  };

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
        {/* Toast de notification */}
        {showToast && (
          <div className={styles.toastContainer}>
            <MessageBar
              className={styles.toast}
              messageBarType={MessageBarType.success}
              isMultiline={false}
              onDismiss={() => setShowToast(false)}
              dismissButtonAriaLabel={localizedStrings.dismiss}
            >
              {toastMessage}
            </MessageBar>
          </div>
        )}
        
        <div className={styles.helpHeader}>
          <h2 className={styles.helpTitle}>
            <Icon iconName="Help" className={styles.titleIcon} />
            {localizedStrings.helpPanelTitle}
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseHelp}
            aria-label={localizedStrings.hide}
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        
        <div className={styles.helpContent}>
          {/* Système d'onglets */}
          <Pivot aria-label="Options d'aide">

          <PivotItem 
              headerText={localizedStrings.guideTab} 
              headerButtonProps={{
                'data-order': 2,
                'data-title': 'Guide'
              }}
              itemIcon="ReadingMode"
            >
              <div className={styles.tabContent}>
                <div className={styles.comingSoon}>
                  <Icon iconName="BuildDefinition" className={styles.comingSoonIcon} />
                  {localizedStrings.comingSoon}
                </div>
              </div>
            </PivotItem>
            
            <PivotItem 
              headerText={localizedStrings.promptsTab} 
              headerButtonProps={{
                'data-order': 1,
                'data-title': 'Prompts'
              }}
              itemIcon="BulletedList"
            >
              <div className={styles.tabContent}>
                <div className={styles.promptsHeader}>
                  <h3 className={styles.promptsTitle}>{localizedStrings.promptsTabTitle}</h3>
                  
                  {/* Barre de recherche */}
                  <div className={styles.searchContainer}>
                    <SearchBox 
                      placeholder={localizedStrings.searchPrompts} 
                      onChange={(_, newValue) => setSearchQuery(newValue || '')}
                      className={styles.searchBox}
                      iconProps={{ iconName: 'Search' }}
                    />
                  </div>
                </div>
                
                {/* Filtres par catégorie */}
                <div className={styles.categoryFilters}>
                  <button 
                    className={`${styles.categoryButton} ${selectedCategory === null ? styles.categoryButtonActive : ''}`}
                    onClick={() => setSelectedCategory(null)}
                  >
                    <Icon iconName="AllApps" className={styles.categoryButtonIcon} />
                    {localizedStrings.allCategories}
                  </button>
                  
                  {categories.map(category => (
                    <button 
                      key={category.key}
                      className={`${styles.categoryButton} ${selectedCategory === category.key ? styles.categoryButtonActive : ''}`}
                      onClick={() => setSelectedCategory(category.key)}
                    >
                      <Icon iconName={category.icon} className={styles.categoryButtonIcon} />
                      {category.name[currentLanguage]}
                    </button>
                  ))}
                </div>
                
                {/* Liste des prompts */}
                <div className={styles.promptsList}>
                  {filteredPrompts.length === 0 ? (
                    <div className={styles.noResults}>
                      <Icon iconName="SearchIssue" className={styles.noResultsIcon} />
                      <div className={styles.noResultsText}>
                        {localizedStrings.noPromptResults}
                      </div>
                    </div>
                  ) : (
                    <FocusZone>
                      <List
                        items={filteredPrompts}
                        onRenderCell={renderPromptItem}
                      />
                    </FocusZone>
                  )}
                </div>
              </div>
            </PivotItem>
            
            <PivotItem 
              headerText={localizedStrings.tipsTab} 
              headerButtonProps={{
                'data-order': 3,
                'data-title': 'Tips'
              }}
              itemIcon="Lightbulb"
            >
              <div className={styles.tabContent}>
                <div className={styles.comingSoon}>
                  <Icon iconName="BuildDefinition" className={styles.comingSoonIcon} />
                  {localizedStrings.comingSoon}
                </div>
              </div>
            </PivotItem>
          </Pivot>
        </div>
      </div>
    </>
  )
}

let localizedStrings = new LocalizedStrings({
  FR: {
    helpPanelTitle: 'Centre d\'aide',
    hide: 'Fermer',
    dismiss: 'Fermer',
    promptCopied: 'Exemple copié dans le presse-papiers!',
    copyError: 'Erreur lors de la copie',
    
    // Onglets
    promptsTab: 'Exemples de prompts',
    guideTab: 'Guide d\'utilisation',
    tipsTab: 'Astuces',
    
    // Contenu de l'onglet Prompts
    promptsTabTitle: 'Exemples de prompts par catégorie',
    searchPrompts: 'Rechercher un prompt...',
    allCategories: 'Toutes les catégories',
    promptLabel: 'Prompt à copier:',
    noPromptResults: 'Aucun prompt ne correspond à votre recherche',
    
    // Message "à venir"
    comingSoon: 'Contenu à venir prochainement...'
  },
  EN: {
    helpPanelTitle: 'Help Center',
    hide: 'Close',
    dismiss: 'Dismiss',
    promptCopied: 'Example copied to clipboard!',
    copyError: 'Error copying to clipboard',
    
    // Tabs
    promptsTab: 'Prompt examples',
    guideTab: 'User guide',
    tipsTab: 'Tips & tricks',
    
    // Prompts tab content
    promptsTabTitle: 'Prompt examples by category',
    searchPrompts: 'Search for a prompt...',
    allCategories: 'All categories',
    promptLabel: 'Prompt to copy:',
    noPromptResults: 'No prompts match your search',
    
    // Coming soon message
    comingSoon: 'Content coming soon...'
  },
});