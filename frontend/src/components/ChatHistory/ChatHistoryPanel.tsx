import { useContext, useEffect } from 'react'
import React from 'react'
import {
  CommandBarButton,
  ContextualMenu,
  DefaultButton,
  Dialog,
  DialogFooter,
  DialogType,
  ICommandBarStyles,
  IContextualMenuItem,
  IStackStyles,
  PrimaryButton,
  Spinner,
  SpinnerSize,
  Stack,
  StackItem,
  Text
} from '@fluentui/react'
import { useBoolean } from '@fluentui/react-hooks'

import { ChatHistoryLoadingState, historyDeleteAll } from '../../api'
import { AppStateContext } from '../../state/AppProvider'

import ChatHistoryList from './ChatHistoryList'

import styles from './ChatHistoryPanel.module.css'

import LocalizedStrings from 'react-localization';

interface ChatHistoryPanelProps {}

export enum ChatHistoryPanelTabs {
  History = 'History'
}

const commandBarStyle: ICommandBarStyles = {
  root: {
    padding: '0',
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: 'transparent'
  }
}

const commandBarButtonStyle: Partial<IStackStyles> = { root: { height: '50px' } }

const localizedStrings = new LocalizedStrings({
  FR: {
    clearAllConfirmation : "Etes-vous sûr de vouloir effacer tout l'historique ?",
    cleaningAllError : "Erreur lors de la suppression de l'historique",
    close: 'Fermer',
    historyWillBeRemoved: "Tout l'historique sera effacé définitivement.",
    pleaseTryAgain: 'Veuillez réessayer. Si le problème persiste, merci de contacter un administrateur.',
    clearAllChatLabel: "Supprimer tout l'historique",
    chathistoryLabel: 'Historique du chat',
    hide: 'Masquer',
    loadError: "Erreur de chargement de l'historique",
    loadingHistory: "Chargement de l'historique",
    clearAll: 'Tout nettoyer',
    cancel: 'Annuler'

  },
  EN: {
    clearAllConfirmation : 'Are you sure you want to clear all chat history?',
    cleaningAllError : 'Error deleting all of chat history',
    close: 'Close',
    historyWillBeRemoved: 'All chat history will be permanently removed.',
    pleaseTryAgain: 'Please try again. If the problem persists, please contact the site administrator.',
    clearAllChatLabel: 'Clear all chat history',
    chathistoryLabel: 'Chat history',
    hide: 'Hide',
    loadError: 'Error loading chat history',
    loadingHistory: 'Loading chat history',
    clearAll: 'Clear all',
    cancel: 'Cancel'

},
  
 });

export function ChatHistoryPanel(_props: ChatHistoryPanelProps) {
  const appStateContext = useContext(AppStateContext)
  const [showContextualMenu, setShowContextualMenu] = React.useState(false)
  const [hideClearAllDialog, { toggle: toggleClearAllDialog }] = useBoolean(true)
  const [clearing, setClearing] = React.useState(false)
  const [clearingError, setClearingError] = React.useState(false)

  const clearAllDialogContentProps = {
    type: DialogType.close,
    title: !clearingError ? localizedStrings.clearAllConfirmation : localizedStrings.cleaningAllError,
    closeButtonAriaLabel: localizedStrings.close,
    subText: !clearingError
      ? localizedStrings.historyWillBeRemoved
      : localizedStrings.pleaseTryAgain
  }

  useEffect(() => {
    localizedStrings.setLanguage((appStateContext?.state.userLanguage) ? appStateContext?.state.userLanguage : 'FR');

  }, [appStateContext?.state.userLanguage])


  const modalProps = {
    titleAriaId: 'labelId',
    subtitleAriaId: 'subTextId',
    isBlocking: true,
    styles: { main: { maxWidth: 450 } }
  }

  const menuItems: IContextualMenuItem[] = [
    { key: 'clearAll', text: localizedStrings.clearAllChatLabel, iconProps: { iconName: 'Delete' } }
  ]

  const handleHistoryClick = () => {
    appStateContext?.dispatch({ type: 'TOGGLE_CHAT_HISTORY' })
  }

  const onShowContextualMenu = React.useCallback((ev: React.MouseEvent<HTMLElement>) => {
    ev.preventDefault() // don't navigate
    setShowContextualMenu(true)
  }, [])

  const onHideContextualMenu = React.useCallback(() => setShowContextualMenu(false), [])

  const onClearAllChatHistory = async () => {
    setClearing(true)
    if (appStateContext?.state.authToken != undefined && appStateContext?.state.authToken != "" ){

      const response = await historyDeleteAll(appStateContext?.state.authToken, appStateContext?.state.encryptedUsername)
      if (!response.ok) {
        setClearingError(true)
      } else {
        appStateContext?.dispatch({ type: 'DELETE_CHAT_HISTORY' })
        toggleClearAllDialog()
      }
    }
    setClearing(false)
  }

  const onHideClearAllDialog = () => {
    toggleClearAllDialog()
    setTimeout(() => {
      setClearingError(false)
    }, 2000)
  }

  React.useEffect(() => {}, [appStateContext?.state.chatHistory, clearingError])

  return (
    <section className={styles.container} data-is-scrollable aria-label={'chat history panel'}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center" wrap aria-label="chat history header">
        <StackItem>
          <Text
            role="heading"
            aria-level={2}
            style={{
              alignSelf: 'center',
              fontWeight: '600',
              fontSize: '18px',
              marginRight: 'auto',
              paddingLeft: '20px'
            }}>
            {localizedStrings.chathistoryLabel}
          </Text>
        </StackItem>
        <Stack verticalAlign="start">
          <Stack horizontal styles={commandBarButtonStyle}>
            <CommandBarButton
              iconProps={{ iconName: 'More' }}
              title={localizedStrings.clearAllChatLabel}
              onClick={onShowContextualMenu}
              aria-label={'clear all chat history'}
              styles={commandBarStyle}
              role="button"
              id="moreButton"
            />
            <ContextualMenu
              items={menuItems}
              hidden={!showContextualMenu}
              target={'#moreButton'}
              onItemClick={toggleClearAllDialog}
              onDismiss={onHideContextualMenu}
            />
            <CommandBarButton
              iconProps={{ iconName: 'Cancel' }}
              title={localizedStrings.hide}
              onClick={handleHistoryClick}
              aria-label={'hide button'}
              styles={commandBarStyle}
              role="button"
            />
          </Stack>
        </Stack>
      </Stack>
      <Stack
        aria-label="chat history panel content"
        styles={{
          root: {
            display: 'flex',
            flexGrow: 1,
            flexDirection: 'column',
            paddingTop: '2.5px',
            maxWidth: '100%'
          }
        }}
        style={{
          display: 'flex',
          flexGrow: 1,
          flexDirection: 'column',
          flexWrap: 'wrap',
          padding: '1px'
        }}>
        <Stack className={styles.chatHistoryListContainer}>
          {appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Success &&
            appStateContext?.state.isCosmosDBAvailable.cosmosDB && <ChatHistoryList />}
          {appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Fail &&
            appStateContext?.state.isCosmosDBAvailable && (
              <>
                <Stack>
                  <Stack horizontalAlign="center" verticalAlign="center" style={{ width: '100%', marginTop: 10 }}>
                    <StackItem>
                      <Text style={{ alignSelf: 'center', fontWeight: '400', fontSize: 16 }}>
                        {appStateContext?.state.isCosmosDBAvailable?.status && (
                          <span>{appStateContext?.state.isCosmosDBAvailable?.status}</span>
                        )}
                        {!appStateContext?.state.isCosmosDBAvailable?.status && <span>{localizedStrings.loadError}</span>}
                      </Text>
                    </StackItem>
                    <StackItem>
                      <Text style={{ alignSelf: 'center', fontWeight: '400', fontSize: 14 }}>
                        <span>Chat history can't be saved at this time</span>
                      </Text>
                    </StackItem>
                  </Stack>
                </Stack>
              </>
            )}
          {appStateContext?.state.chatHistoryLoadingState === ChatHistoryLoadingState.Loading && (
            <>
              <Stack>
                <Stack
                  horizontal
                  horizontalAlign="center"
                  verticalAlign="center"
                  style={{ width: '100%', marginTop: 10 }}>
                  <StackItem style={{ justifyContent: 'center', alignItems: 'center' }}>
                    <Spinner
                      style={{ alignSelf: 'flex-start', height: '100%', marginRight: '5px' }}
                      size={SpinnerSize.medium}
                    />
                  </StackItem>
                  <StackItem>
                    <Text style={{ alignSelf: 'center', fontWeight: '400', fontSize: 14 }}>
                      <span style={{ whiteSpace: 'pre-wrap' }}>{localizedStrings.loadingHistory}</span>
                    </Text>
                  </StackItem>
                </Stack>
              </Stack>
            </>
          )}
        </Stack>
      </Stack>
      <Dialog
        hidden={hideClearAllDialog}
        onDismiss={clearing ? () => {} : onHideClearAllDialog}
        dialogContentProps={clearAllDialogContentProps}
        modalProps={modalProps}>
        <DialogFooter>
          {!clearingError && <PrimaryButton onClick={onClearAllChatHistory} disabled={clearing} text={localizedStrings.clearAll} />}
          <DefaultButton
            onClick={onHideClearAllDialog}
            disabled={clearing}
            text={!clearingError ? localizedStrings.cancel : localizedStrings.close}
          />
        </DialogFooter>
      </Dialog>
    </section>
  )
}
