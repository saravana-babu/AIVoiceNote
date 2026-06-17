import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  useWindowDimensions,
} from 'react-native';
import { Text, Divider, useTheme } from 'react-native-paper';
import { Button, Card, Input } from '@voicemind/ui';
import {
  useKnowledgeCollectionsQuery,
  useCreateCollectionMutation,
  useDeleteCollectionMutation,
  useKnowledgeSourcesQuery,
  useUploadSourceMutation,
  useDeleteSourceMutation,
  useSearchKnowledgeQuery,
  useChatKnowledgeMutation,
} from '../hooks/useKnowledge.js';
import { useSyncStore } from '../store/syncStore.js';
import { KnowledgeCollection, KnowledgeSource } from '@voicemind/api';

const MOCK_DOC_TEMPLATES = [
  {
    filename: 'Phoenix_Project_Brief.md',
    mimeType: 'text/markdown',
    label: '📄 Project Phoenix Brief (Markdown)',
    content: `# Project Phoenix - Cloud Migration Initiative
Project Phoenix is our core enterprise cloud migration project. 
The main goal is to migrate all database and server workloads from on-premises to GCP by Q4 2026.
The key contact is Sarah Jenkins (Lead Cloud Architect). The estimated budget is $1.2M.
This project references Client Acme Corp who is requesting a highly available setup.`,
  },
  {
    filename: 'Client_Acme_Feedback.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    label: '💼 Acme Corp Feedback (DOCX)',
    content: `Acme Corp Dashboard Requirements
The client Acme Corp requested a progress update on Project Phoenix.
They are highly concerned about security and offline synchronization conflicts.
John Doe is scheduled to meet Acme Corp stakeholders next Tuesday to review conflict resolution policies.
Acme Corp discusses their upcoming expansion plans in Europe.`,
  },
  {
    filename: 'GCP_Migration_Plan.pdf',
    mimeType: 'application/pdf',
    label: '📕 GCP Architecture Plan (PDF)',
    content: `Google Cloud Platform Migration Design
For Project Phoenix, we will employ a hybrid cloud architecture.
We will migrate PostgreSQL databases first, setting up pgvector to support AI search capabilities.
Primary blockers are latency issues between legacy systems and the new GCP region.
This design follows up on Action Item #12: Configure GCP secure endpoints.`,
  },
];

export function KnowledgeHubView() {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const isOnline = useSyncStore((state) => state.isOnline);

  // States
  const [selectedCol, setSelectedCol] = useState<KnowledgeCollection | null>(null);
  const [selectedSource, setSelectedSource] = useState<KnowledgeSource | null>(null);
  const [newColName, setNewColName] = useState('');
  const [newColDesc, setNewColDesc] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [chatMessage, setChatMessage] = useState('');
  
  // Chat History state
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; citations?: any[] }>>([]);

  // Fetch Collections & Sources
  const { data: collections = [], isLoading: isLoadingCols } = useKnowledgeCollectionsQuery();
  const { data: sources = [], isLoading: isLoadingSources } = useKnowledgeSourcesQuery(selectedCol?.id);

  // Mutations
  const createCollection = useCreateCollectionMutation();
  const deleteCollection = useDeleteCollectionMutation();
  const uploadSource = useUploadSourceMutation();
  const deleteSource = useDeleteSourceMutation(selectedCol?.id);
  const chatKnowledge = useChatKnowledgeMutation();

  // Search hook
  const { data: searchResults = [], isLoading: isLoadingSearch } = useSearchKnowledgeQuery(
    searchQuery,
    selectedCol?.id,
    selectedSource?.id
  );

  const handleCreateCollection = async () => {
    if (!newColName.trim()) {
      alert('Please enter a collection name');
      return;
    }
    try {
      await createCollection.mutateAsync({
        name: newColName.trim(),
        description: newColDesc.trim() || undefined,
      });
      setNewColName('');
      setNewColDesc('');
      alert('Collection created!');
    } catch (err: any) {
      alert(err.message || 'Failed to create collection');
    }
  };

  const handleDeleteCollection = async (id: string) => {
    try {
      await deleteCollection.mutateAsync(id);
      if (selectedCol?.id === id) {
        setSelectedCol(null);
      }
      alert('Collection deleted');
    } catch (err: any) {
      alert(err.message || 'Failed to delete collection');
    }
  };

  const handleSimulateUpload = async (template: typeof MOCK_DOC_TEMPLATES[0]) => {
    if (!isOnline) {
      alert('You must be online to upload files');
      return;
    }
    try {
      // In a real device we would use FileSystem, here we pass simulated content path
      // Our ApiClient expects fileUri, name, mimeType.
      // We pass the contents as fileUri (custom URI schema handled by backend or simply indexing via text)
      // Since our backend endpoint POST /sources/upload takes a file upload,
      // in React Native we build a FormData. Fetch handles files using a fake URI or Blob.
      // We simulate file upload using template filename and body text.
      // Our API client converts file object to FormData.
      // For testing, we create a mock file representation:
      // We pass data URI containing template content.
      const dataUri = `data:text/plain;base64,${btoa(template.content)}`;
      
      await uploadSource.mutateAsync({
        fileUri: dataUri,
        filename: template.filename,
        mimeType: template.mimeType,
        collectionId: selectedCol?.id,
      });
      alert(`Successfully parsed and indexed: ${template.filename}`);
    } catch (err: any) {
      alert(err.message || 'Failed to upload document');
    }
  };

  const handleDeleteSource = async (id: string) => {
    try {
      await deleteSource.mutateAsync(id);
      if (selectedSource?.id === id) {
        setSelectedSource(null);
      }
      alert('Document deleted');
    } catch (err: any) {
      alert(err.message || 'Failed to delete document');
    }
  };

  const handleSendMessage = async (msgOverride?: string) => {
    const textToSend = msgOverride || chatMessage;
    if (!textToSend.trim()) return;

    if (!isOnline) {
      alert('You must be online to chat with the knowledge base');
      return;
    }

    const userMsg = { role: 'user' as const, content: textToSend };
    setChatMessages((prev) => [...prev, userMsg]);
    if (!msgOverride) {
      setChatMessage('');
    }

    try {
      const history = chatMessages.map(m => ({ role: m.role, content: m.content }));
      const res = await chatKnowledge.mutateAsync({
        message: textToSend,
        collectionId: selectedCol?.id,
        sourceId: selectedSource?.id,
        chatHistory: history,
      });

      const assistantMsg = {
        role: 'assistant' as const,
        content: res.response,
        citations: res.citations,
      };
      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `⚠️ Error: ${err.message || 'Failed to get answer'}` },
      ]);
    }
  };

  const handleCitationPress = (citation: any) => {
    // Search source inside collections/sources list or fetch
    // Then set it as the active selected source for viewer
    const src = sources.find(s => s.id === citation.id);
    if (src) {
      setSelectedSource(src);
    } else {
      // Create a temporary source details structure for display
      setSelectedSource({
        id: citation.id,
        title: citation.title,
        source_type: citation.source_type,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        note_id: citation.note_id,
      });
    }
  };

  const clearChat = () => {
    setChatMessages([]);
  };

  // UI Render Components

  const renderChatArea = () => {
    return (
      <Card style={StyleSheet.flatten([styles.chatCard, { backgroundColor: theme.colors.elevation.level1 }])}>
        <View style={styles.chatHeader}>
          <View>
            <Text variant="titleMedium" style={{ fontWeight: '700' }}>
              💬 AI Knowledge Chat
            </Text>
            <Text variant="bodySmall" style={{ color: theme.colors.secondary }}>
              Scope:{' '}
              {selectedSource
                ? `Source: ${selectedSource.title}`
                : selectedCol
                ? `Collection: ${selectedCol.name}`
                : 'Entire Knowledge Base'}
            </Text>
          </View>
          {chatMessages.length > 0 && (
            <TouchableOpacity onPress={clearChat}>
              <Text style={{ color: theme.colors.primary, fontSize: 13, fontWeight: '600' }}>
                Clear Chat
              </Text>
            </TouchableOpacity>
          )}
        </View>

        <Divider style={{ marginVertical: 8 }} />

        <ScrollView
          style={{ flex: 1, minHeight: 250, maxHeight: 400 }}
          contentContainerStyle={{ gap: 12, paddingVertical: 8 }}
        >
          {chatMessages.length === 0 ? (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', opacity: 0.6, paddingVertical: 40 }}>
              <Text variant="titleMedium" style={{ marginBottom: 4 }}>
                Ask anything!
              </Text>
              <Text variant="bodyMedium" style={{ textAlign: 'center', paddingHorizontal: 20 }}>
                Query your meetings, transcripts, and documents. Use templates below to seed data if empty.
              </Text>
            </View>
          ) : (
            chatMessages.map((msg, idx) => (
              <View
                key={idx}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  backgroundColor:
                    msg.role === 'user' ? theme.colors.primary : 'rgba(255, 255, 255, 0.05)',
                  padding: 12,
                  borderRadius: 12,
                  maxWidth: '85%',
                }}
              >
                <Text style={{ color: msg.role === 'user' ? '#FFFFFF' : theme.colors.onSurface, lineHeight: 18 }}>
                  {msg.content}
                </Text>
                
                {/* Citations display */}
                {msg.citations && msg.citations.length > 0 && (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, paddingTop: 6, borderTopWidth: 1, borderColor: 'rgba(255,255,255,0.08)' }}>
                    <Text variant="bodySmall" style={{ color: theme.colors.secondary, alignSelf: 'center', fontSize: 10 }}>
                      Sources:
                    </Text>
                    {msg.citations.map((c) => (
                      <TouchableOpacity
                        key={c.id}
                        onPress={() => handleCitationPress(c)}
                        style={{
                          backgroundColor: 'rgba(20, 184, 166, 0.15)',
                          borderRadius: 4,
                          paddingHorizontal: 6,
                          paddingVertical: 2,
                        }}
                      >
                        <Text style={{ color: '#14B8A6', fontSize: 10, fontWeight: '700' }}>
                          [{c.index}] {c.title.split('.')[0]}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>
            ))
          )}
          {chatKnowledge.isPending && (
            <View style={{ alignSelf: 'flex-start', padding: 12, flexDirection: 'row', gap: 8 }}>
              <ActivityIndicator size="small" color={theme.colors.primary} />
              <Text style={{ color: theme.colors.secondary }}>Assistant is thinking...</Text>
            </View>
          )}
        </ScrollView>

        {/* Suggested Questions */}
        {chatMessages.length > 0 && chatMessages[chatMessages.length - 1].role === 'assistant' && (
          <View style={{ marginVertical: 8 }}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexDirection: 'row', gap: 6 }}>
              {['What are the blockers?', 'Summarize the next steps', 'Are there any client decisions?'].map((q) => (
                <TouchableOpacity
                  key={q}
                  onPress={() => handleSendMessage(q)}
                  style={{
                    backgroundColor: 'rgba(255,255,255,0.03)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    borderRadius: 12,
                    paddingHorizontal: 10,
                    paddingVertical: 4,
                    marginRight: 6,
                  }}
                >
                  <Text style={{ fontSize: 11, color: theme.colors.primary }}>{q}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}

        <Divider style={{ marginVertical: 8 }} />

        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Input
            label=""
            placeholder={
              selectedSource
                ? `Chat with ${selectedSource.title}...`
                : selectedCol
                ? `Chat with collection ${selectedCol.name}...`
                : "Chat with entire Knowledge Base..."
            }
            value={chatMessage}
            onChangeText={setChatMessage}
            style={{ flex: 1 }}
          />
          <Button
            title="Send"
            onPress={() => handleSendMessage()}
            disabled={!isOnline || chatKnowledge.isPending}
            style={{ alignSelf: 'center', height: 46 }}
          />
        </View>
      </Card>
    );
  };

  const renderSourceViewer = () => {
    if (!selectedSource) {
      return (
        <Card style={StyleSheet.flatten([styles.viewerCard, { backgroundColor: theme.colors.elevation.level1 }])}>
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', opacity: 0.5, padding: 32 }}>
            <Text variant="titleMedium" style={{ marginBottom: 4 }}>
              No Source Selected
            </Text>
            <Text variant="bodyMedium" style={{ textAlign: 'center' }}>
              Select a document or transcript from the list on the left to read its contents and explore linked entities.
            </Text>
          </View>
        </Card>
      );
    }

    return (
      <Card style={StyleSheet.flatten([styles.viewerCard, { backgroundColor: theme.colors.elevation.level1 }])}>
        <View style={styles.viewerHeader}>
          <View style={{ flex: 1 }}>
            <Text variant="titleMedium" style={{ fontWeight: '700' }}>
              📖 {selectedSource.title}
            </Text>
            <Text variant="bodySmall" style={{ color: theme.colors.secondary }}>
              Type: {selectedSource.source_type.toUpperCase()} • Indexed:{' '}
              {new Date(selectedSource.created_at).toLocaleDateString()}
            </Text>
          </View>
          <TouchableOpacity onPress={() => setSelectedSource(null)}>
            <Text style={{ color: theme.colors.primary, fontWeight: '700' }}>Close</Text>
          </TouchableOpacity>
        </View>

        <Divider style={{ marginVertical: 8 }} />

        <ScrollView style={{ flex: 1, maxHeight: 300 }}>
          <Text variant="bodyMedium" style={{ lineHeight: 22, opacity: 0.9 }}>
            {selectedSource.raw_content || 'No text content extracted for this node placeholder.'}
          </Text>
        </ScrollView>

        {/* Related Entity links */}
        <View style={{ marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderColor: 'rgba(255,255,255,0.08)' }}>
          <Text variant="titleSmall" style={{ fontWeight: '700', marginBottom: 8 }}>
            🕸️ Linked Knowledge Graph relationships
          </Text>
          
          {/* Simulated relationships list based on text analysis */}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {selectedSource.title.includes('Phoenix') && (
              <>
                <TouchableOpacity
                  onPress={() => handleCitationPress({ id: 'acme-id', title: 'Acme Corp Feedback.docx', source_type: 'docx' })}
                  style={styles.relBadge}
                >
                  <Text style={styles.relText}>discusses Client: Acme Corp</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() => handleCitationPress({ id: 'gcp-id', title: 'GCP Architecture Plan.pdf', source_type: 'pdf' })}
                  style={styles.relBadge}
                >
                  <Text style={styles.relText}>referenced_by GCP Architecture Plan</Text>
                </TouchableOpacity>
              </>
            )}
            {selectedSource.title.includes('Acme') && (
              <TouchableOpacity
                onPress={() => handleCitationPress({ id: 'phoenix-id', title: 'Phoenix_Project_Brief.md', source_type: 'markdown' })}
                style={styles.relBadge}
              >
                <Text style={styles.relText}>member_of Project: Phoenix</Text>
              </TouchableOpacity>
            )}
            {selectedSource.title.includes('GCP') && (
              <TouchableOpacity
                onPress={() => handleCitationPress({ id: 'phoenix-id', title: 'Phoenix_Project_Brief.md', source_type: 'markdown' })}
                style={styles.relBadge}
              >
                <Text style={styles.relText}>follows_up Project: Phoenix</Text>
              </TouchableOpacity>
            )}
            {!selectedSource.title.includes('Phoenix') && !selectedSource.title.includes('Acme') && !selectedSource.title.includes('GCP') && (
              <Text variant="bodySmall" style={{ color: theme.colors.secondary, fontStyle: 'italic' }}>
                No relationships detected for this item.
              </Text>
            )}
          </View>
        </View>
      </Card>
    );
  };

  const renderLeftPanel = () => {
    return (
      <View style={{ gap: 16 }}>
        {/* Collections List */}
        <Card style={{ padding: 12, backgroundColor: theme.colors.elevation.level1 }}>
          <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 12 }}>
            📂 Collections
          </Text>
          {isLoadingCols ? (
            <ActivityIndicator size="small" color={theme.colors.primary} />
          ) : (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {/* Entire Base selector */}
              <TouchableOpacity
                onPress={() => {
                  setSelectedCol(null);
                  setSelectedSource(null);
                }}
                style={[
                  styles.collectionPill,
                  {
                    backgroundColor: !selectedCol
                      ? theme.colors.primary
                      : 'rgba(255, 255, 255, 0.05)',
                  },
                ]}
              >
                <Text
                  style={{
                    color: !selectedCol ? '#FFFFFF' : theme.colors.secondary,
                    fontWeight: '700',
                    fontSize: 12,
                  }}
                >
                  🌐 Entire Base
                </Text>
              </TouchableOpacity>

              {collections.map((col) => {
                const isSelected = selectedCol?.id === col.id;
                return (
                  <TouchableOpacity
                    key={col.id}
                    onPress={() => {
                      setSelectedCol(col);
                      setSelectedSource(null);
                    }}
                    style={[
                      styles.collectionPill,
                      {
                        backgroundColor: isSelected
                          ? theme.colors.primary
                          : 'rgba(255, 255, 255, 0.05)',
                      },
                    ]}
                  >
                    <Text
                      style={{
                        color: isSelected ? '#FFFFFF' : theme.colors.secondary,
                        fontWeight: '700',
                        fontSize: 12,
                      }}
                    >
                      📁 {col.name}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}

          {/* Create custom collection */}
          <Divider style={{ marginVertical: 12 }} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Input
              label=""
              placeholder="New Collection name..."
              value={newColName}
              onChangeText={setNewColName}
              style={{ flex: 1, height: 38 }}
            />
            <Button
              title="Add"
              onPress={handleCreateCollection}
              style={{ height: 38, paddingVertical: 0 }}
            />
          </View>
        </Card>

        {/* Document indexing templates */}
        <Card style={{ padding: 12, backgroundColor: theme.colors.elevation.level1 }}>
          <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 6 }}>
            ➕ Index Documents
          </Text>
          <Text variant="bodySmall" style={{ color: theme.colors.secondary, marginBottom: 12 }}>
            Simulate uploading files into the active collection ({selectedCol?.name || 'Research'}).
          </Text>
          <View style={{ gap: 8 }}>
            {MOCK_DOC_TEMPLATES.map((tmpl, idx) => (
              <TouchableOpacity
                key={idx}
                onPress={() => handleSimulateUpload(tmpl)}
                style={styles.templateBtn}
              >
                <Text style={{ color: theme.colors.primary, fontSize: 13, fontWeight: '600' }}>
                  {tmpl.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>

        {/* Sources/Documents List */}
        <Card style={{ padding: 12, backgroundColor: theme.colors.elevation.level1 }}>
          <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 12 }}>
            📄 Indexed Sources ({sources.length})
          </Text>
          {isLoadingSources ? (
            <ActivityIndicator size="small" color={theme.colors.primary} />
          ) : sources.length === 0 ? (
            <Text style={{ color: theme.colors.secondary, fontStyle: 'italic', paddingVertical: 8 }}>
              No indexed sources in this scope. Click templates above to load.
            </Text>
          ) : (
            <ScrollView style={{ maxHeight: 200 }} contentContainerStyle={{ gap: 6 }}>
              {sources.map((src) => {
                const isSelected = selectedSource?.id === src.id;
                return (
                  <View key={src.id} style={styles.sourceRow}>
                    <TouchableOpacity
                      onPress={() => setSelectedSource(src)}
                      style={{ flex: 1 }}
                    >
                      <Text
                        style={{
                          color: isSelected ? theme.colors.primary : theme.colors.onSurface,
                          fontWeight: isSelected ? '700' : '400',
                          fontSize: 13,
                        }}
                      >
                        {src.source_type === 'pdf' ? '📕' : src.source_type === 'docx' ? '📘' : '📝'}{' '}
                        {src.title}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => handleDeleteSource(src.id)}>
                      <Text style={{ color: '#EF4444', fontSize: 11 }}>Delete</Text>
                    </TouchableOpacity>
                  </View>
                );
              })}
            </ScrollView>
          )}
        </Card>
      </View>
    );
  };

  const renderSearchArea = () => {
    return (
      <Card style={{ padding: 12, backgroundColor: theme.colors.elevation.level1 }}>
        <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 8 }}>
          🔍 Knowledge Search
        </Text>
        <Input
          label=""
          placeholder="Hybrid semantic query across chunks..."
          value={searchQuery}
          onChangeText={setSearchQuery}
          style={{ marginBottom: 8 }}
        />
        {searchQuery.trim().length > 0 && (
          <View style={{ marginTop: 8 }}>
            <Text variant="titleSmall" style={{ fontWeight: '700', marginBottom: 6 }}>
              Ranked Chunk Results:
            </Text>
            {isLoadingSearch ? (
              <ActivityIndicator size="small" color={theme.colors.primary} />
            ) : searchResults.length === 0 ? (
              <Text style={{ color: theme.colors.secondary, fontStyle: 'italic' }}>
                No chunks matched query.
              </Text>
            ) : (
              <ScrollView style={{ maxHeight: 150 }} contentContainerStyle={{ gap: 8 }}>
                {searchResults.map((res, idx) => (
                  <TouchableOpacity
                    key={idx}
                    onPress={() => handleCitationPress({ id: res.source_id, title: res.source_title, source_type: res.source_type })}
                    style={{
                      padding: 8,
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      borderRadius: 6,
                    }}
                  >
                    <Text style={{ fontWeight: '700', fontSize: 12, color: theme.colors.primary }}>
                      [{idx + 1}] {res.source_title} (Score: {res.score.toFixed(3)})
                    </Text>
                    <Text numberOfLines={2} style={{ fontSize: 11, color: theme.colors.secondary, marginTop: 2 }}>
                      {res.content}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}
          </View>
        )}
      </Card>
    );
  };

  if (isDesktop) {
    // Desktop Split-Screen Layout
    return (
      <View style={styles.desktopContainer}>
        {/* Left Side: Navigation panel */}
        <View style={styles.desktopLeft}>
          {renderLeftPanel()}
        </View>

        {/* Right Side: Chat and document viewing */}
        <View style={styles.desktopRight}>
          {renderSearchArea()}
          <View style={{ flexDirection: 'row', gap: 16, flex: 1, marginTop: 16 }}>
            <View style={{ flex: 1 }}>
              {renderChatArea()}
            </View>
            <View style={{ flex: 1 }}>
              {renderSourceViewer()}
            </View>
          </View>
        </View>
      </View>
    );
  }

  // Mobile/Tablet stacked layout
  return (
    <ScrollView contentContainerStyle={{ gap: 16, padding: 16 }}>
      {renderLeftPanel()}
      {renderSearchArea()}
      {renderChatArea()}
      {renderSourceViewer()}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  desktopContainer: {
    flexDirection: 'row',
    gap: 16,
    padding: 16,
    flex: 1,
  },
  desktopLeft: {
    width: 320,
    gap: 16,
  },
  desktopRight: {
    flex: 1,
    gap: 0,
  },
  collectionPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
  },
  templateBtn: {
    padding: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderColor: 'rgba(255, 255, 255, 0.08)',
    borderWidth: 1,
    borderRadius: 8,
  },
  sourceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.04)',
  },
  chatCard: {
    padding: 12,
    borderRadius: 12,
    flex: 1,
  },
  chatHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  viewerCard: {
    padding: 12,
    borderRadius: 12,
    flex: 1,
  },
  viewerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  relBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderColor: 'rgba(255,255,255,0.1)',
    borderWidth: 1,
    borderRadius: 6,
  },
  relText: {
    fontSize: 11,
    color: '#818CF8',
  },
});
