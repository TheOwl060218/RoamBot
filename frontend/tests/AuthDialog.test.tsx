import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { AuthProvider } from '../src/features/auth/AuthProvider'
import { AuthDialog } from '../src/features/auth/AuthDialog'

describe('AuthDialog', () => {
  beforeEach(() => {
    vi.spyOn(apiClient, 'me').mockResolvedValue(null)
  })

  it('offers username and password login without verification fields', async () => {
    const user = userEvent.setup()
    render(
      <AuthProvider>
        <AuthDialog open onClose={vi.fn()} />
      </AuthProvider>,
    )

    expect(screen.getByRole('dialog', { name: '登录 RoamBot' })).toBeInTheDocument()
    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
    expect(screen.queryByText(/手机号|短信|验证码|邮箱|找回密码/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '创建账户' }))
    expect(screen.getByRole('button', { name: '注册并登录' })).toBeInTheDocument()
  })

  it('closes on Escape and can reveal the password without changing it', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <AuthProvider>
        <AuthDialog open onClose={onClose} />
      </AuthProvider>,
    )

    const password = screen.getByLabelText('密码')
    await user.type(password, 'password123')
    await user.click(screen.getByRole('button', { name: '显示密码' }))
    expect(password).toHaveAttribute('type', 'text')
    expect(password).toHaveValue('password123')

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })
})
