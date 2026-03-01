import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      
      login: async (email, password) => {
        // 这里后续会调用实际API
        const mockUser = {
          id: '1',
          email,
          name: '张三',
          familyName: '张家投资组合',
          role: 'admin'
        }
        const mockToken = 'mock-jwt-token'
        
        set({ 
          user: mockUser, 
          token: mockToken, 
          isAuthenticated: true 
        })
        
        return { success: true }
      },
      
      register: async (email, password, name) => {
        // 这里后续会调用实际API
        const mockUser = {
          id: '1',
          email,
          name,
          familyName: `${name}的家庭`,
          role: 'admin'
        }
        const mockToken = 'mock-jwt-token'
        
        set({ 
          user: mockUser, 
          token: mockToken, 
          isAuthenticated: true 
        })
        
        return { success: true }
      },
      
      logout: () => {
        set({ 
          user: null, 
          token: null, 
          isAuthenticated: false 
        })
      },
      
      updateProfile: (updates) => {
        const currentUser = get().user
        if (currentUser) {
          set({ user: { ...currentUser, ...updates } })
        }
      }
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        user: state.user, 
        token: state.token, 
        isAuthenticated: state.isAuthenticated 
      }),
    }
  )
)
