import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { DoctorView } from './components/DoctorView'
import { PatientView } from './components/PatientView'
import './index.css'

// ?theme=NAME picks one of the themes in theme.css for this browser and remembers it; ?theme=default forgets it.
try {
  const asked = new URLSearchParams(location.search).get('theme')
  if (asked === 'default') localStorage.removeItem('medbridge.theme')
  else if (asked) localStorage.setItem('medbridge.theme', asked)
  const theme = localStorage.getItem('medbridge.theme')
  if (theme) {
    document.documentElement.dataset.theme = theme
    // a name with no block in theme.css would leave the page uncoloured: fall back to the default
    if (!getComputedStyle(document.documentElement).getPropertyValue('--patient-page').trim()) delete document.documentElement.dataset.theme
  }
} catch { /* storage blocked: the default theme is used */ }

const isDoctor = location.pathname.startsWith('/doctor')
document.title = isDoctor ? 'Medbridge · Clinician' : 'Medbridge · Patient'

createRoot(document.getElementById('root')!).render(
  <StrictMode>{isDoctor ? <DoctorView /> : <PatientView />}</StrictMode>,
)
