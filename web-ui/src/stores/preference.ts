import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPreference, setPreference } from '@/api/client'

export interface NodePosition {
    x: number
    y: number
}

export interface TopologyLayout {
    [nodeId: string]: NodePosition
}

export const usePreferenceStore = defineStore('preference', () => {
    const topologyLayout = ref<TopologyLayout>({})
    const isLoading = ref(false)

    async function loadTopologyLayout() {
        isLoading.value = true
        try {
            const res = await getPreference('topology_layout')
            if (res.value) {
                topologyLayout.value = res.value
            }
        } catch (error) {
            console.error('Failed to load topology layout:', error)
        } finally {
            isLoading.value = false
        }
    }

    async function saveTopologyLayout(layout: TopologyLayout) {
        // 乐观更新
        topologyLayout.value = { ...topologyLayout.value, ...layout }
        try {
            await setPreference('topology_layout', topologyLayout.value)
        } catch (error) {
            console.error('Failed to save topology layout:', error)
        }
    }

    async function updateNodePosition(nodeId: string, x: number, y: number) {
        const newLayout = { ...topologyLayout.value, [nodeId]: { x, y } }
        topologyLayout.value = newLayout
        try {
            await setPreference('topology_layout', newLayout)
        } catch (error) {
            console.error('Failed to update node position:', error)
        }
    }

    return {
        topologyLayout,
        isLoading,
        loadTopologyLayout,
        saveTopologyLayout,
        updateNodePosition
    }
})
