import React, { useEffect, useState } from 'react'
import { deleteByFilePath, deleteBySite, getUploadedFiles, getDataGouvernorats, getDataDelegations, getDataSecteurs } from '../api/client'
import CascadingLocationSelect from './CascadingLocationSelect.jsx'

export default function AdminDeleteTools() {
  const [files, setFiles] = useState([])
  const [selectedFileId, setSelectedFileId] = useState('')
  const [siteSelection, setSiteSelection] = useState({ secteurId: null })
  const [result, setResult] = useState(null)
  const [confirming, setConfirming] = useState(null) // 'path' | 'site' | null

  const loadFiles = () => getUploadedFiles().then(setFiles).catch(() => setFiles([]))
  useEffect(() => { loadFiles() }, [])

  const selectedFile = files.find((f) => String(f.id) === selectedFileId)

  const runDeleteByPath = async () => {
    if (!selectedFile) return
    const res = await deleteByFilePath(selectedFile.archive_path)
    setResult(`Fichier "${selectedFile.original_filename}" supprime : ${res.deleted_rows} lignes retirees de la base.`)
    setSelectedFileId('')
    setConfirming(null)
    loadFiles()
  }

  const runDeleteBySite = async () => {
    if (!siteSelection.secteurId) return
    const res = await deleteBySite(siteSelection.secteurId)
    setResult(`Secteur supprime : ${res.deleted_rows} lignes retirees (tous types de test).`)
    setSiteSelection({ secteurId: null })
    setConfirming(null)
    loadFiles()
  }

  return (
    <div className="panel" style={{ padding: 24 }}>
      <div className="eyebrow" style={{ marginBottom: 16 }}>Suppression de donnees</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--text-muted)' }}>
            Supprimer un fichier importe
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <select value={selectedFileId} onChange={(e) => setSelectedFileId(e.target.value)} style={{ flex: 1 }}>
              <option value="">
                {files.length === 0 ? 'Aucun fichier importe' : 'Choisir un fichier'}
              </option>
              {files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.original_filename} — {f.operator}/{f.technology || '?'} ({f.log_type}) — {f.majority_secteur_name || 'non archive'}
                </option>
              ))}
            </select>
            {confirming !== 'path' ? (
              <button className="btn-danger" disabled={!selectedFileId} onClick={() => setConfirming('path')}>
                Supprimer
              </button>
            ) : (
              <>
                <button className="btn-danger" onClick={runDeleteByPath}>Confirmer</button>
                <button className="btn-ghost" onClick={() => setConfirming(null)}>Annuler</button>
              </>
            )}
          </div>
          {selectedFile && (
            <div className="mono" style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 6 }}>
              {selectedFile.archive_path || 'non archive (secteur non resolu lors de l\'import)'}
            </div>
          )}
        </div>

        <div>
          <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--text-muted)' }}>
            Supprimer toutes les donnees d'un site (Secteur)
          </div>
          <CascadingLocationSelect
            fetchGouvernorats={getDataGouvernorats}
            fetchDelegations={getDataDelegations}
            fetchSecteurs={getDataSecteurs}
            emptyGouvernoratMessage="Aucune donnee importee"
            onSelectionChange={setSiteSelection}
          />
          <div style={{ marginTop: 10 }}>
            {confirming !== 'site' ? (
              <button className="btn-danger" disabled={!siteSelection.secteurId} onClick={() => setConfirming('site')}>
                Supprimer ce secteur
              </button>
            ) : (
              <>
                <button className="btn-danger" onClick={runDeleteBySite}>Confirmer</button>
                <button className="btn-ghost" onClick={() => setConfirming(null)} style={{ marginLeft: 8 }}>Annuler</button>
              </>
            )}
          </div>
        </div>
      </div>

      {result && (
        <div style={{ marginTop: 16, fontSize: 13, color: 'var(--signal-good)' }}>{result}</div>
      )}
    </div>
  )
}
