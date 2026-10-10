import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { DoctorView } from './components/DoctorView'
import { PatientView } from './components/PatientView'
import './index.css'

const isDoctor = location.pathname.startsWith('/doctor')
document.title = isDoctor ? 'Medbridge · Clinician' : 'Medbridge · Patient'

createRoot(document.getElementById('root')!).render(
  <StrictMode>{isDoctor ? <DoctorView /> : <PatientView />}</StrictMode>,
)
