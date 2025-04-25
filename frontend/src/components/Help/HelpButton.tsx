import { DefaultButton, IButtonProps } from '@fluentui/react'
import styles from './HelpButton.module.css'

interface ButtonProps extends IButtonProps {
  onClick: () => void
  text: string | undefined
}

export const HelpButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.helpButton}
      text={text}
      onClick={onClick}
    />
  )
}