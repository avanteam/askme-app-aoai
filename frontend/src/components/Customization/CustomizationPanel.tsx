import React, { useContext, useEffect, useState, useRef } from 'react'
import {
  Icon,
  Text,
  Stack,
  Slider,
  ChoiceGroup,
  IChoiceGroupOption,
  MessageBar,
  MessageBarType
} from '@fluentui/react'
import { AppStateContext } from '../../state/AppProvider'

// Importation des fichiers de style
import styles from './CustomizationPanel.module.css'

// Types pour les préférences de personnalisation
export interface CustomizationPreferences {
  responseSize: 'veryShort' | 'medium' | 'comprehensive';
  documentsCount: number;
}

export function CustomizationPanel() {
  const appStateContext = useContext(AppStateContext)
  const [isVisible, setIsVisible] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const [currentLanguage, setCurrentLanguage] = useState('FR')
  
  // États pour les préférences utilisateur
  const [responseSize, setResponseSize] = useState<'veryShort' | 'medium' | 'comprehensive'>(
    appStateContext?.state.customizationPreferences?.responseSize || 'medium'
  )
  
  const [documentsCount, setDocumentsCount] = useState<number>(
    appStateContext?.state.customizationPreferences?.documentsCount || 5
  )
  
  const panelRef = useRef<HTMLDivElement>(null)
  
  // Options pour le choix de la taille de réponse
  const responseSizeOptions: IChoiceGroupOption[] = [
    { key: 'veryShort', text: currentLanguage === 'FR' ? 'Très courte' : 'Very short' },
    { key: 'medium', text: currentLanguage === 'FR' ? 'Moyenne' : 'Medium' },
    { key: 'comprehensive', text: currentLanguage === 'FR' ? 'Très complète' : 'Comprehensive' }
  ]
  
  // Fermeture du panneau de personnalisation
  const handleCloseCustomization = () => {
    setIsVisible(false)
    // Délai avant de réellement masquer le panneau (pour permettre l'animation)
    setTimeout(() => {
      appStateContext?.dispatch({ type: 'TOGGLE_CUSTOMIZATION_PANEL' })
    }, 300)
  }
  
  // Enregistrement des préférences utilisateur
  const savePreferences = () => {
    const preferences: CustomizationPreferences = {
      responseSize,
      documentsCount
    }
    
    // Mise à jour des préférences dans le contexte global
    appStateContext?.dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: preferences })
    
    // Afficher un toast de confirmation
    setToastMessage(currentLanguage === 'FR' ? 'Préférences enregistrées avec succès!' : 'Preferences saved successfully!')
    setShowToast(true)
    
    // Masquer après 3 secondes
    setTimeout(() => {
      setShowToast(false)
    }, 3000)
  }
  
  // Gestion du clic sur l'overlay (fond semi-transparent)
  const handleOverlayClick = (e: React.MouseEvent) => {
    // S'assurer que le clic était bien sur l'overlay et pas sur le panneau
    if (e.target === e.currentTarget) {
      handleCloseCustomization()
    }
  }
  
  // Réinitialiser les paramètres par défaut
  const resetToDefaults = () => {
    const defaultPreferences: CustomizationPreferences = {
      responseSize: 'medium',
      documentsCount: 5
    }
    
    // Mettre à jour l'état local
    setResponseSize('medium')
    setDocumentsCount(5)
    
    // Mettre à jour l'état global
    appStateContext?.dispatch({ type: 'UPDATE_CUSTOMIZATION_PREFERENCES', payload: defaultPreferences })
    
    // Afficher un toast de confirmation
    setToastMessage(currentLanguage === 'FR' ? 'Préférences réinitialisées' : 'Preferences reset to defaults')
    setShowToast(true)
    
    // Masquer après 3 secondes
    setTimeout(() => {
      setShowToast(false)
    }, 3000)
  }

  useEffect(() => {
    // Définir l'animation d'apparition après montage du composant
    setTimeout(() => {
      setIsVisible(true)
    }, 50)
    
    // Déterminer la langue en fonction du contexte de l'application
    const userLang = appStateContext?.state.userLanguage || 'FR';
    setCurrentLanguage(userLang);
    
    // Synchroniser l'état local avec les préférences globales à chaque ouverture du panneau
    if (appStateContext?.state.customizationPreferences) {
      setResponseSize(appStateContext.state.customizationPreferences.responseSize);
      setDocumentsCount(appStateContext.state.customizationPreferences.documentsCount);
    }
    
    // Ajouter l'écouteur pour la touche Escape
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseCustomization()
      }
    }
    
    document.addEventListener('keydown', handleEscapeKey)
    
    // Nettoyage lors du démontage
    return () => {
      document.removeEventListener('keydown', handleEscapeKey)
    }
  }, [appStateContext?.state.userLanguage, appStateContext?.state.customizationPreferences])

  return (
    <>
      {/* Overlay semi-transparent */}
      <div 
        className={`${styles.overlay} ${isVisible ? styles.overlayVisible : ''}`}
        onClick={handleOverlayClick}
        aria-hidden="true"
      />
      
      {/* Panneau de personnalisation */}
      <div 
        ref={panelRef}
        className={`${styles.container} ${isVisible ? styles.visible : ''}`} 
        aria-label="panneau de personnalisation"
      >
        {/* Toast de notification */}
        {showToast && (
          <div className={styles.toastContainer}>
            <MessageBar
              className={styles.toast}
              messageBarType={MessageBarType.success}
              isMultiline={false}
              onDismiss={() => setShowToast(false)}
              dismissButtonAriaLabel={currentLanguage === 'FR' ? 'Fermer' : 'Dismiss'}
            >
              {toastMessage}
            </MessageBar>
          </div>
        )}
        
        <div className={styles.customizationHeader}>
          <h2 className={styles.customizationTitle}>
            <Icon iconName="Settings" className={styles.titleIcon} />
            {currentLanguage === 'FR' ? 'Personnalisation' : 'Customization'}
          </h2>
          <button 
            className={styles.closeButton} 
            onClick={handleCloseCustomization}
            aria-label={currentLanguage === 'FR' ? 'Fermer' : 'Close'}
          >
            <Icon iconName="Cancel" />
          </button>
        </div>
        
        <div className={styles.customizationContent}>
          {/* Section de la taille de réponse */}
          <div className={styles.settingSection}>
            <h3 className={styles.settingTitle}>
              <Icon iconName="TextDocument" className={styles.settingIcon} />
              {currentLanguage === 'FR' ? 'Taille de la réponse' : 'Response Size'}
            </h3>
            <p className={styles.settingDescription}>
              {currentLanguage === 'FR' 
                ? 'Choisissez la longueur des réponses générées par l\'assistant.' 
                : 'Choose the length of responses generated by the assistant.'}
            </p>
            
            <ChoiceGroup 
              selectedKey={responseSize}
              options={responseSizeOptions}
              onChange={(_, option) => option && setResponseSize(option.key as any)}
              className={styles.choiceGroup}
            />
          </div>
          
          {/* Section du nombre de documents */}
          <div className={styles.settingSection}>
            <h3 className={styles.settingTitle}>
              <Icon iconName="DocumentSearch" className={styles.settingIcon} />
              {currentLanguage === 'FR' ? 'Nombre de documents' : 'Number of Documents'}
            </h3>
            <p className={styles.settingDescription}>
              {currentLanguage === 'FR' 
                ? 'Définissez combien de documents l\'assistant doit consulter pour répondre à vos questions.' 
                : 'Set how many documents the assistant should consult to answer your questions.'}
            </p>
            
            <div className={styles.sliderContainer}>
              <Slider
                label={`${documentsCount} ${currentLanguage === 'FR' ? 'documents' : 'documents'}`}
                min={3}
                max={20}
                step={1}
                value={documentsCount}
                onChange={setDocumentsCount}
                showValue={false}
                className={styles.slider}
              />
              <div className={styles.sliderLegend}>
                <span className={styles.sliderMin}>3</span>
                <span className={styles.sliderMax}>20</span>
              </div>
            </div>
          </div>
          
          {/* Boutons d'action */}
          <div className={styles.actionButtons}>
            <button 
              className={styles.saveButton}
              onClick={savePreferences}
            >
              <Icon iconName="Save" className={styles.buttonIcon} />
              {currentLanguage === 'FR' ? 'Enregistrer' : 'Save'}
            </button>
            
            <button 
              className={styles.resetButton}
              onClick={resetToDefaults}
            >
              <Icon iconName="Refresh" className={styles.buttonIcon} />
              {currentLanguage === 'FR' ? 'Réinitialiser' : 'Reset'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}