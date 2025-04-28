import { CommandBarButton, DefaultButton, IButtonProps, TooltipHost  } from '@fluentui/react'

import styles from './Button.module.css'

interface ButtonProps extends IButtonProps {
  onClick: () => void
  text: string | undefined
}

export const ShareButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <CommandBarButton
      className={styles.shareButtonRoot}
      iconProps={{ iconName: 'Share' }}
      onClick={onClick}
      text={text}
    />
  )
}

export const HistoryButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.historyButtonRoot}
      text={text}
      iconProps={{ iconName: 'History' }}
      onClick={onClick}
    />
  )
}

export const ExportButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <TooltipHost content="Exporter la conversation au format PDF">
      <CommandBarButton
        className={styles.exportButtonRoot}
        iconProps={{ iconName: 'PDF' }}
        onClick={onClick}
        text={text}
      />
    </TooltipHost>
  )
}

export const HelpButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.helpButtonRoot}
      text={text}
      iconProps={{ iconName: 'Lifesaver' }}
      onClick={onClick}
    />
  )
}