export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: number
  nome: string
  email: string
  ativo: boolean
  created_at: string
}

export interface DatabaseHealth {
  status: string
  database: string
}
