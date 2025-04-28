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
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AppStateContext } from '../../state/AppProvider'

// Importation des fichiers de style
import styles from './HelpPanel.module.css'

// Importation du contenu d'aide
import {
  guideContent,
  predefinedPrompts,
  categories,
  translations,
  GuideSection,
  PredefinedPrompt
} from './helpContent'

import LocalizedStrings from 'react-localization';

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
  const [selectedGuideSection, setSelectedGuideSection] = useState<string>('getting-started')
  const panelRef = useRef<HTMLDivElement>(null)
  const guideSectionRefs = useRef<{[key: string]: React.RefObject<HTMLDivElement>}>({})
  
  // Initialisation des références localisées
  const localizedStrings = new LocalizedStrings(translations);
  
  // Initialisation des refs pour chaque section du guide
  useEffect(() => {
    guideContent.forEach(section => {
      guideSectionRefs.current[section.id] = React.createRef<HTMLDivElement>();
    });
  }, []);
  
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

  // Fonction pour faire défiler vers une section du guide
  const scrollToGuideSection = (sectionId: string) => {
    setSelectedGuideSection(sectionId);
    
    const sectionRef = guideSectionRefs.current[sectionId];
    if (sectionRef && sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

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

  // Rendu d'une section du guide
  const renderGuideSection = (section: GuideSection) => {
    return (
      <div 
        key={section.id} 
        ref={guideSectionRefs.current[section.id]}
        className={styles.sectionContainer}
        id={`guide-section-${section.id}`}
      >
        <h3 className={styles.sectionTitle}>
          <Icon iconName={section.icon} />
          {section.title[currentLanguage]}
        </h3>
        
        <div className={styles.markdownContent}>
          <ReactMarkdown
            children={section.content[currentLanguage]}
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({node, ...props}) => <p className={styles.markdownParagraph} {...props} />,
              ul: ({node, ...props}) => <ul className={styles.markdownList} {...props} />,
              ol: ({node, ...props}) => <ol className={styles.markdownList} {...props} />,
              li: ({node, ...props}) => <li className={styles.markdownListItem} {...props} />,
              strong: ({node, ...props}) => <strong className={styles.markdownBold} {...props} />
            }}
          />
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
                'data-order': 1,
                'data-title': 'Guide'
              }}
              itemIcon="ReadingMode"
            >
              <div className={styles.tabContent}>
                {/* Navigation du guide */}
                <div className={styles.guideNavigation}>
                  {guideContent.map(section => (
                    <button
                      key={section.id}
                      className={`${styles.guideNavButton} ${selectedGuideSection === section.id ? styles.guideNavButtonActive : ''}`}
                      onClick={() => scrollToGuideSection(section.id)}
                    >
                      <Icon iconName={section.icon} className={styles.guideNavButtonIcon} />
                      {section.title[currentLanguage]}
                    </button>
                  ))}
                </div>
                
                {/* Contenu du guide */}
                <div style={{ overflow: 'auto' }}>
                  {guideContent.map(section => renderGuideSection(section))}
                </div>
              </div>
            </PivotItem>
            
            <PivotItem 
              headerText={localizedStrings.promptsTab} 
              headerButtonProps={{
                'data-order': 2,
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
            
          </Pivot>
        </div>
      </div>
    </>
  )
}