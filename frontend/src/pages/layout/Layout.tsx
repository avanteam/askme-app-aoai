import { useContext, useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { Dialog, Stack, TextField } from '@fluentui/react'
import { CopyRegular } from '@fluentui/react-icons'

import { CosmosDBStatus } from '../../api'
import Contoso from '../../assets/Contoso.svg'
import { HistoryButton, ShareButton, ExportButton } from '../../components/common/Button'
import { AppStateContext } from '../../state/AppProvider'
import { exportToPdf } from '../../utils/exportToPdf'

import styles from './Layout.module.css'

import LocalizedStrings from 'react-localization';

const Layout = () => {
  const [isSharePanelOpen, setIsSharePanelOpen] = useState<boolean>(false)
  const [copyClicked, setCopyClicked] = useState<boolean>(false)
  const [copyText, setCopyText] = useState<string>(localizedStrings.copyUrl)
  const [shareLabel, setShareLabel] = useState<string | undefined>(localizedStrings.share)
  const [exportLabel, setExportLabel] = useState<string | undefined>(localizedStrings.export)
  const [hideHistoryLabel, setHideHistoryLabel] = useState<string>(localizedStrings.hideHistory)
  const [showHistoryLabel, setShowHistoryLabel] = useState<string>(localizedStrings.showHistory)
  const [logo, setLogo] = useState('')
  const appStateContext = useContext(AppStateContext)
  const ui = appStateContext?.state.frontendSettings?.ui

  const handleShareClick = () => {
    setIsSharePanelOpen(true)
  }

  const handleExportClick = () => {
    if (appStateContext?.state.currentChat?.messages) {
      try {
        // Filter out non-user and non-assistant messages
        const filteredMessages = appStateContext.state.currentChat.messages.filter(
          msg => msg.role === 'user' || msg.role === 'assistant'
        );
        
        if (filteredMessages.length === 0) {
          console.error("No valid messages to export");
          return;
        }
        
        const title = appStateContext.state.currentChat.title || localizedStrings.conversationExport
        const date = new Date().toISOString().split('T')[0]
        const filename = `${title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${date}.pdf`
        
        exportToPdf(filteredMessages, {
          filename,
          title,
          locale: appStateContext?.state.userLanguage?.toLowerCase() || 'fr-fr',
          singlePage: true 
        })
      } catch (error) {
        console.error("Error generating PDF:", error);
      }
    }
  }

  const handleSharePanelDismiss = () => {
    setIsSharePanelOpen(false)
    setCopyClicked(false)
    setCopyText(localizedStrings.copyUrl)
  }

  const handleCopyClick = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopyClicked(true)
  }

  const handleHistoryClick = () => {
    appStateContext?.dispatch({ type: 'TOGGLE_CHAT_HISTORY' })
  }

  useEffect(() => {
    if (!appStateContext?.state.isLoading) {
      setLogo(ui?.logo || Contoso)
    }
  }, [appStateContext?.state.isLoading])

  useEffect(() => {
    if (copyClicked) {
      setCopyText(localizedStrings.copiedUrl)
    }
  }, [copyClicked])

  useEffect(() => {
    localizedStrings.setLanguage((appStateContext?.state.userLanguage) ? appStateContext?.state.userLanguage : 'FR');
    setShareLabel(localizedStrings.share)
    setExportLabel(localizedStrings.export)
    setHideHistoryLabel(localizedStrings.hideHistory)
    setShowHistoryLabel(localizedStrings.showHistory)
   }, [appStateContext?.state.userLanguage])

  useEffect(() => { }, [appStateContext?.state.isCosmosDBAvailable.status])

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 480) {
        setShareLabel(undefined)
        setExportLabel(undefined)
        setHideHistoryLabel(localizedStrings.hideHistory)
        setShowHistoryLabel(localizedStrings.showHistory)
      } else {
        setShareLabel(localizedStrings.share)
        setExportLabel(localizedStrings.export)
        setHideHistoryLabel(localizedStrings.hideHistory)
        setShowHistoryLabel(localizedStrings.showHistory)
      }
    }

    window.addEventListener('resize', handleResize)
    handleResize()

    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const isExportDisabled = !appStateContext?.state.currentChat?.messages || appStateContext.state.currentChat.messages.length === 0

  return (
    <div className={styles.layout}>
      <header className={styles.header} role={'banner'}>
        <Stack horizontal verticalAlign="center" horizontalAlign="space-between">
          <Stack horizontal verticalAlign="center">
            <img src={logo} className={styles.headerIcon} aria-hidden="true" alt="" />
            <Link to="/" className={styles.headerTitleContainer}>
              <h1 className={styles.headerTitle}>{ui?.title}</h1>
            </Link>
          </Stack>
          <Stack horizontal tokens={{ childrenGap: 4 }} className={styles.shareButtonContainer}>
            {appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && ui?.show_chat_history_button !== false && (
              <HistoryButton
                onClick={handleHistoryClick}
                text={appStateContext?.state?.isChatHistoryOpen ? hideHistoryLabel : showHistoryLabel}
              />
            )}
            {appStateContext?.state.currentChat?.messages && appStateContext.state.currentChat.messages.length > 0 && (
              <ExportButton 
                onClick={handleExportClick}
                text={exportLabel}
              />
            )}
            {ui?.show_share_button && <ShareButton onClick={handleShareClick} text={shareLabel} />}
          </Stack>
        </Stack>
      </header>
      <Outlet />
      <Dialog
        onDismiss={handleSharePanelDismiss}
        hidden={!isSharePanelOpen}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '600px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '200px',
                  minHeight: '100px'
                }
              }
            }
          ]
        }}
        dialogContentProps={{
          title: localizedStrings.shareWebApp,
          showCloseButton: true
        }}>
        <Stack horizontal verticalAlign="center" style={{ gap: '8px' }}>
          <TextField className={styles.urlTextBox} defaultValue={window.location.href} readOnly />
          <div
            className={styles.copyButtonContainer}
            role="button"
            tabIndex={0}
            aria-label="Copy"
            onClick={handleCopyClick}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? handleCopyClick() : null)}>
            <CopyRegular className={styles.copyButton} />
            <span className={styles.copyButtonText}>{copyText}</span>
          </div>
        </Stack>
      </Dialog>
    </div>
  )
}

let localizedStrings = new LocalizedStrings({
  FR: {
      hideHistory : "Masquer historique",
      showHistory : "Afficher historique",
      copyUrl : "Copier l'URL",
      copiedUrl : "URL copiée",
      share : "Partager",
      export : "Exporter",
      shareWebApp: "Partager l'app web",
      conversationExport: "Export de conversation"
  },
  EN: {
    hideHistory : "Hide history",
    showHistory : "Show history",
    copyUrl : "Copy URL",
    copiedUrl : "Copied URL",
    share: "Share",
    export: "Export",
    shareWebApp: "Share the web app",
    conversationExport: "Conversation Export"
},
  
 });

export default Layout