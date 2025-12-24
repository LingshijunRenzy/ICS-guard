<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type { TopologyResponse, TopologyNode, TopologyLink, UiEventItem } from '@/api/client'
import { fetchTopology } from '@/api/client'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import * as d3 from 'd3-force'

interface NodeObject {
  id: string
  threeGroup: THREE.Group
  data: TopologyNode
  x: number
  y: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
  degree: number
}

interface LinkObject {
  source: NodeObject | string
  target: NodeObject | string
  threeMesh: THREE.Mesh
  data: TopologyLink
  originalColor: THREE.Color
}

interface FlowAnimation {
  id: string
  mesh: THREE.Mesh
  sourceNode: NodeObject
  targetNode: NodeObject
  path: NodeObject[]
  progress: number
  startTime: number
  duration: number
  blocked?: boolean
  blockedLabel?: THREE.Sprite
  glitchStartTime?: number
}

const loading = ref(false)
const topologyData = ref<TopologyResponse | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const tooltipRef = ref<HTMLElement | null>(null)
const tooltipContent = ref('')
const tooltipVisible = ref(false)
const tooltipPos = ref({ x: 0, y: 0 })
const selectedNode = ref<TopologyNode | null>(null)
const selectedLink = ref<LinkObject | null>(null)
const selectedHighlight: { group: THREE.Group | null } = { group: null }

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let animationId: number
let raycaster: THREE.Raycaster
let mouse: THREE.Vector2
let isDragging = false
let isDraggingNode = false
let dragStart = new THREE.Vector2()
let dragStartMouse = new THREE.Vector2()
let cameraOffset = new THREE.Vector3(0, 0, 0)
let draggedNode: NodeObject | null = null
const dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)

const nodeObjects: Map<string, NodeObject> = new Map()
const linkObjects: LinkObject[] = []
let simulation: d3.Simulation<NodeObject, LinkObject>
let ws: WebSocket | null = null
const flowAnimations: Map<string, FlowAnimation> = new Map()
let hoveredLink: LinkObject | null = null
let hoveredNode: NodeObject | null = null

const CONFIG = {
  nodeSize: 55,
  heightRatio: 0.5,
  cameraMinHeight: 200,
  cameraMaxHeight: 2000,
  cameraInitialHeight: 800,
  colors: {
    switch: '#2DFEFF',
    router: '#E020F0',
    server: '#0064FF',
    plc: '#FFA500',
    hmi: '#00FF9C',
    sensor: '#FFFFFF',
    actuator: '#FF2A6D',
    firewall: '#FF0000',
    default: '#808080'
  } as Record<string, string>,
  statusColors: {
    online: '#FFFFFF',
    offline: '#909399',
    error: '#FF2A6D',
    warning: '#FFE600',
    unknown: '#C0C4CC'
  } as Record<string, string>
}

const initThree = () => {
  if (!containerRef.value) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  scene = new THREE.Scene()

  const aspect = width / height
  camera = new THREE.PerspectiveCamera(75, aspect, 1, 5000)

  camera.position.set(0, CONFIG.cameraInitialHeight, 0)
  camera.lookAt(0, 0, 0)
  camera.updateProjectionMatrix()
  cameraOffset.y = CONFIG.cameraInitialHeight

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  containerRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.enableRotate = false
  controls.enablePan = false
  controls.enableZoom = false
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.DOLLY,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: null as any
  }

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()

  renderer.domElement.addEventListener('mousemove', onMouseMove)
  renderer.domElement.addEventListener('mousedown', onMouseDown)
  renderer.domElement.addEventListener('mouseup', onMouseUp)
  renderer.domElement.addEventListener('click', onMouseClick)
  renderer.domElement.addEventListener('wheel', onMouseWheel, { passive: false })
  window.addEventListener('resize', onWindowResize)

  animate()
}

const createCornerWireframe = (size: number, height: number, cornerLength: number, material: THREE.LineBasicMaterial): THREE.Group => {
  const cornerGroup = new THREE.Group()
  const halfSize = size / 2
  const halfHeight = height / 2

  const corners: [number, number, number][] = [
    [-halfSize, halfHeight, -halfSize],
    [halfSize, halfHeight, -halfSize],
    [-halfSize, -halfHeight, -halfSize],
    [halfSize, -halfHeight, -halfSize],
    [-halfSize, halfHeight, halfSize],
    [halfSize, halfHeight, halfSize],
    [-halfSize, -halfHeight, halfSize],
    [halfSize, -halfHeight, halfSize]
  ]

  corners.forEach((corner) => {
    const [x, y, z] = corner
    const points: THREE.Vector3[] = []

    const xDir = x < 0 ? cornerLength : -cornerLength
    const yDir = y < 0 ? cornerLength : -cornerLength
    const zDir = z < 0 ? cornerLength : -cornerLength

    points.push(new THREE.Vector3(x, y, z))
    points.push(new THREE.Vector3(x + xDir, y, z))

    points.push(new THREE.Vector3(x, y, z))
    points.push(new THREE.Vector3(x, y + yDir, z))

    points.push(new THREE.Vector3(x, y, z))
    points.push(new THREE.Vector3(x, y, z + zDir))

    const geometry = new THREE.BufferGeometry().setFromPoints(points)
    const line = new THREE.LineSegments(geometry, material)
    line.userData.isCorner = true
    cornerGroup.add(line)
  })

  return cornerGroup
}

const createTopBottomCornerWireframe = (size: number, height: number, cornerLength: number, material: THREE.LineBasicMaterial): THREE.Group => {
  const cornerGroup = new THREE.Group()
  const halfSize = size / 2
  const halfHeight = height / 2

  const topCorners: [number, number, number][] = [
    [-halfSize, halfHeight, -halfSize],
    [halfSize, halfHeight, -halfSize],
    [-halfSize, halfHeight, halfSize],
    [halfSize, halfHeight, halfSize]
  ]

  const bottomCorners: [number, number, number][] = [
    [-halfSize, -halfHeight, -halfSize],
    [halfSize, -halfHeight, -halfSize],
    [-halfSize, -halfHeight, halfSize],
    [halfSize, -halfHeight, halfSize]
  ]

  const renderCorners = (corners: [number, number, number][]) => {
    corners.forEach((corner) => {
      const [x, y, z] = corner
      const points: THREE.Vector3[] = []

      const xDir = x < 0 ? cornerLength : -cornerLength
      const zDir = z < 0 ? cornerLength : -cornerLength

      points.push(new THREE.Vector3(x, y, z))
      points.push(new THREE.Vector3(x + xDir, y, z))

      points.push(new THREE.Vector3(x, y, z))
      points.push(new THREE.Vector3(x, y, z + zDir))

      const geometry = new THREE.BufferGeometry().setFromPoints(points)
      const line = new THREE.LineSegments(geometry, material)
      cornerGroup.add(line)
    })
  }

  renderCorners(topCorners)
  renderCorners(bottomCorners)

  return cornerGroup
}

const createNodeMesh = (node: TopologyNode, degree: number): THREE.Group => {
  const group = new THREE.Group()
  const size = CONFIG.nodeSize
  const height = size * CONFIG.heightRatio

  const type = node.type.toLowerCase()
  const baseColorHex = CONFIG.colors[type] || CONFIG.colors.default
  const baseColor = new THREE.Color(baseColorHex)

  const cornerLength = size * 0.15

  const borderMaterial = new THREE.LineBasicMaterial({
    color: 0xffffff,
    linewidth: 2,
    transparent: true,
    opacity: 0.8
  })

  const cornerMaterial = new THREE.LineBasicMaterial({
    color: 0xffffff,
    linewidth: 3.5,
    transparent: true,
    opacity: 0.8
  })

  const geometry = new THREE.BoxGeometry(size, height, size)
  const edges = new THREE.EdgesGeometry(geometry)
  const wireframe = new THREE.LineSegments(edges, borderMaterial)
  group.add(wireframe)

  const cornerWireframe = createCornerWireframe(size, height, cornerLength, cornerMaterial)
  group.add(cornerWireframe)

  const planeGeo = new THREE.PlaneGeometry(size - 2, size - 2)
  const planeMat = new THREE.MeshBasicMaterial({
    color: baseColor,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.6
  })
  const plane = new THREE.Mesh(planeGeo, planeMat)
  plane.rotation.x = -Math.PI / 2
  plane.position.y = -height / 2 + 0.1
  group.add(plane)

  const normalizedDegree = Math.min(degree, 20) / 20
  const coreSize = size * (0.3 + 0.2 * normalizedDegree)
  const coreHeight = coreSize * 0.5

  const coreGeo = new THREE.BoxGeometry(coreSize, coreHeight, coreSize)
  const coreMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.8 + 0.2 * normalizedDegree,
    side: THREE.FrontSide
  })
  const core = new THREE.Mesh(coreGeo, coreMat)
  group.add(core)

  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (ctx) {
    canvas.width = 512
    canvas.height = 128
    ctx.font = 'bold 48px "0xProto Nerd Font", monospace'
    ctx.fillStyle = 'white'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.shadowColor = 'rgba(0, 0, 0, 0.8)'
    ctx.shadowBlur = 8
    ctx.fillText(node.name, 256, 64)

    const texture = new THREE.CanvasTexture(canvas)
    const spriteMat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthTest: false,
      depthWrite: false
    })
    const sprite = new THREE.Sprite(spriteMat)
    sprite.center.set(0.5, 0) // 底部中心对齐
    sprite.position.y = size * 0.6
    sprite.userData.isLabel = true
    sprite.userData.baseScale = { x: 120, y: 30 }
    sprite.renderOrder = 999
    group.add(sprite)
  }

  group.userData = { isNode: true, id: node.id, data: node }

  return group
}

const createLinkMesh = (): THREE.Mesh => {
  // 使用圆柱体作为连线，初始高度为1，之后通过 scale.y 调整长度
  // 旋转几何体使得 Cylinder 沿 Z 轴对齐，以便使用 lookAt
  const geometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 8)
  geometry.rotateX(-Math.PI / 2) // 旋转后，高度沿 Z 轴

  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.4
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.userData.isLink = true
  return mesh
}

const findConnectedComponents = (nodes: TopologyNode[], links: TopologyLink[]): string[][] => {
  const nodeMap = new Map<string, TopologyNode>()
  nodes.forEach(node => nodeMap.set(node.id, node))

  const adjacencyList = new Map<string, string[]>()
  nodes.forEach(node => adjacencyList.set(node.id, []))

  links.forEach(link => {
    const sourceList = adjacencyList.get(link.source) || []
    const targetList = adjacencyList.get(link.target) || []
    if (!sourceList.includes(link.target)) sourceList.push(link.target)
    if (!targetList.includes(link.source)) targetList.push(link.source)
    adjacencyList.set(link.source, sourceList)
    adjacencyList.set(link.target, targetList)
  })

  const visited = new Set<string>()
  const components: string[][] = []

  const dfs = (nodeId: string, component: string[]) => {
    visited.add(nodeId)
    component.push(nodeId)
    const neighbors = adjacencyList.get(nodeId) || []
    neighbors.forEach(neighborId => {
      if (!visited.has(neighborId)) {
        dfs(neighborId, component)
      }
    })
  }

  nodes.forEach(node => {
    if (!visited.has(node.id)) {
      const component: string[] = []
      dfs(node.id, component)
      components.push(component)
    }
  })

  return components
}

const updateTopology = (data: TopologyResponse) => {
  nodeObjects.forEach(obj => scene.remove(obj.threeGroup))
  linkObjects.forEach(obj => scene.remove(obj.threeMesh))
  nodeObjects.clear()
  linkObjects.length = 0

  const degrees = new Map<string, number>()
  data.links.forEach(link => {
    degrees.set(link.source, (degrees.get(link.source) || 0) + 1)
    degrees.set(link.target, (degrees.get(link.target) || 0) + 1)
  })

  const components = findConnectedComponents(data.nodes, data.links)
  const componentCenters = new Map<string, { x: number; y: number }>()

  const componentSpacing = 150
  const componentsPerRow = Math.ceil(Math.sqrt(components.length))

  components.forEach((component, index) => {
    const row = Math.floor(index / componentsPerRow)
    const col = index % componentsPerRow
    const centerX = (col - (componentsPerRow - 1) / 2) * componentSpacing
    const centerY = (row - (components.length / componentsPerRow - 1) / 2) * componentSpacing

    component.forEach(nodeId => {
      componentCenters.set(nodeId, { x: centerX, y: centerY })
    })
  })

  const d3Nodes: NodeObject[] = data.nodes.map(node => {
    const degree = degrees.get(node.id) || 0
    const group = createNodeMesh(node, degree)
    scene.add(group)

    const center = componentCenters.get(node.id) || { x: 0, y: 0 }
    const offsetX = (Math.random() - 0.5) * 100
    const offsetY = (Math.random() - 0.5) * 100

    const nodeObj: NodeObject = {
      id: node.id,
      threeGroup: group,
      data: node,
      x: center.x + offsetX,
      y: center.y + offsetY,
      degree
    }
    nodeObjects.set(node.id, nodeObj)

    return nodeObj
  })

  const d3Links = data.links.map(link => {
    const sourceNode = nodeObjects.get(link.source)
    const targetNode = nodeObjects.get(link.target)

    if (sourceNode && targetNode) {
      const mesh = createLinkMesh()

      scene.add(mesh)
      const linkObj: LinkObject = {
        source: sourceNode,
        target: targetNode,
        threeMesh: mesh,
        data: link,
        originalColor: new THREE.Color(0xffffff)
      }
      linkObjects.push(linkObj)
      return linkObj
    }
    return null
  }).filter(Boolean) as LinkObject[]

  if (simulation) simulation.stop()

  const componentMap = new Map<string, number>()
  components.forEach((component, index) => {
    component.forEach(nodeId => {
      componentMap.set(nodeId, index)
    })
  })

  simulation = d3.forceSimulation(d3Nodes)
    .force('link', d3.forceLink(d3Links).id((d: any) => d.id).distance(200))
    .force('charge', d3.forceManyBody().strength(-1000))
    .force('center', d3.forceCenter(0, 0).strength(0.1))
    .force('collide', d3.forceCollide(CONFIG.nodeSize * 1.5))
    .force('component', (alpha: number) => {
      const componentPositions = new Map<number, { x: number; y: number; count: number }>()

      d3Nodes.forEach(node => {
        const compId = componentMap.get(node.id) ?? -1
        if (!componentPositions.has(compId)) {
          componentPositions.set(compId, { x: 0, y: 0, count: 0 })
        }
        const pos = componentPositions.get(compId)!
        pos.x += node.x
        pos.y += node.y
        pos.count += 1
      })

      componentPositions.forEach((pos, compId) => {
        pos.x /= pos.count
        pos.y /= pos.count
      })

      d3Nodes.forEach(node => {
        const compId = componentMap.get(node.id) ?? -1
        const compCenter = componentPositions.get(compId)
        if (compCenter && compId >= 0) {
          const dx = compCenter.x - node.x
          const dy = compCenter.y - node.y
          const distance = Math.sqrt(dx * dx + dy * dy)
          if (distance > 0) {
            const strength = alpha * 0.05
            node.vx = (node.vx || 0) + dx * strength
            node.vy = (node.vy || 0) + dy * strength
          }
        }
      })
    })
    .on('tick', () => {
      d3Nodes.forEach(node => {
        if (node.fx !== undefined && node.fx !== null && node.fy !== undefined && node.fy !== null) {
          node.x = node.fx
          node.y = node.fy
        }
        node.threeGroup.position.set(node.x, 0, node.y)

        if (selectedNode.value && selectedNode.value.id === node.id && selectedHighlight.group) {
          selectedHighlight.group.position.set(node.x, 0, node.y)
        }
      })

      linkObjects.forEach(link => {
        if (!link.threeMesh) return

        const source = link.source as NodeObject
        const target = link.target as NodeObject

        if (!source || !target) return

        const start = new THREE.Vector3(source.x, 0, source.y)
        const end = new THREE.Vector3(target.x, 0, target.y)

        // 计算中点
        const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
        link.threeMesh.position.copy(mid)

        // 计算长度
        const distance = start.distanceTo(end)
        link.threeMesh.scale.z = distance

        // 朝向目标
        link.threeMesh.lookAt(end)
      })
    })
}

const findPath = (sourceId: string, targetId: string): NodeObject[] | null => {
  if (sourceId === targetId) {
    const node = nodeObjects.get(sourceId)
    return node ? [node] : null
  }

  const queue: { node: NodeObject; path: NodeObject[] }[] = []
  const visited = new Set<string>()

  const sourceNode = nodeObjects.get(sourceId)
  if (!sourceNode) return null

  queue.push({ node: sourceNode, path: [sourceNode] })
  visited.add(sourceId)

  while (queue.length > 0) {
    const { node, path } = queue.shift()!

    for (const link of linkObjects) {
      const linkSource = link.source as NodeObject
      const linkTarget = link.target as NodeObject

      let other: NodeObject | null = null
      if (linkSource.id === node.id) {
        other = linkTarget
      } else if (linkTarget.id === node.id) {
        other = linkSource
      }

      if (other && !visited.has(other.id)) {
        visited.add(other.id)
        const newPath = [...path, other]

        if (other.id === targetId) {
          return newPath
        }

        queue.push({ node: other, path: newPath })
      }
    }
  }

  return null
}

const createFlowAnimation = (sourceId: string, targetId: string, pathHops?: any[], blocked?: boolean): void => {
  const sourceNode = nodeObjects.get(sourceId)
  const targetNode = nodeObjects.get(targetId)

  if (!sourceNode || !targetNode) return

  let path: NodeObject[] | null = null

  if (pathHops && pathHops.length > 0) {
    // 尝试使用 path_hops 构建路径
    const hopPath: NodeObject[] = []
    
    for (const hop of pathHops) {
      const nodeId = hop.node_id
      const node = nodeObjects.get(nodeId)
      if (node) {
        hopPath.push(node)
      }
    }

    if (hopPath.length > 0) {
      path = hopPath
    }
  }

  // 如果没有 path_hops 或构建失败，回退到 BFS 寻路
  if (!path || path.length < 2) {
    path = findPath(sourceId, targetId)
  }
  
  if (!path || path.length < 2) return

  const flowId = `flow_${Date.now()}_${Math.random()}`
  const flowSize = CONFIG.nodeSize * 0.1
  const flowGeo = new THREE.BoxGeometry(flowSize, flowSize, flowSize)
  const flowMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, // 恢复默认白色，不因 blocked 变色
    transparent: true,
    opacity: 0.9
  })
  const flowMesh = new THREE.Mesh(flowGeo, flowMat)
  flowMesh.position.set(sourceNode.x, 0, sourceNode.y)
  scene.add(flowMesh)

  const duration = 2000
  const animation: FlowAnimation = {
    id: flowId,
    mesh: flowMesh,
    sourceNode,
    targetNode,
    path,
    progress: 0,
    startTime: Date.now(),
    duration,
    blocked
  }

  flowAnimations.set(flowId, animation)

  // 如果被阻断，不需要自动销毁，由 updateFlowAnimations 控制
  if (!blocked) {
    setTimeout(() => {
      if (flowMesh && flowMesh.parent) {
        scene.remove(flowMesh)
        if (flowMesh.geometry) flowMesh.geometry.dispose()
        if (flowMesh.material) flowMesh.material.dispose()
      }
      flowAnimations.delete(flowId)
    }, duration)
  }
}

const createBlockedLabel = (position: THREE.Vector3): THREE.Sprite => {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (ctx) {
    canvas.width = 512
    canvas.height = 128
    
    // 正红色背景
    ctx.fillStyle = '#FF0000'
    ctx.fillRect(0, 0, 512, 128)
    
    // 文字
    ctx.font = 'bold 64px "0xProto Nerd Font", monospace'
    ctx.fillStyle = '#000000'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('BLOCKED!', 256, 64)

    const texture = new THREE.CanvasTexture(canvas)
    const spriteMat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthTest: false,
      depthWrite: false
    })
    const sprite = new THREE.Sprite(spriteMat)
    sprite.position.copy(position)
    sprite.position.y += 40 // 悬浮在上方
    sprite.scale.set(120, 30, 1)
    return sprite
  }
  return new THREE.Sprite()
}

const updateFlowAnimations = () => {
  const now = Date.now()

  flowAnimations.forEach((anim) => {
    if (!anim.mesh || !anim.mesh.parent) {
      return
    }

    const elapsed = now - anim.startTime
    anim.progress = Math.min(1, elapsed / anim.duration)

    // 如果被阻断且到达终点（或接近终点）
    if (anim.blocked) {
      // 寻找路径中最后一个 switch 节点
      let stopIndex = -1
      for (let i = anim.path.length - 1; i >= 0; i--) {
        const node = anim.path[i]
        if (node && node.data.type.toLowerCase() === 'switch') {
          stopIndex = i
          break
        }
      }

      let shouldStop = false
      let stopNode: NodeObject | null = null

      if (stopIndex !== -1) {
        // 存在 switch 节点，计算到达该节点的进度
        // 路径总段数 = path.length - 1
        // 到达 stopIndex 节点的段数 = stopIndex
        const targetProgress = stopIndex / (anim.path.length - 1)
        
        // 允许一点误差，或者直接判断是否超过
        if (anim.progress >= targetProgress) {
          shouldStop = true
          stopNode = anim.path[stopIndex] || null
        }
      } else {
        // 没有 switch 节点，在 50% 处拦截
        if (anim.progress >= 0.5) {
          shouldStop = true
          // 计算 50% 处的坐标作为停止点
          // 这里简单处理：直接使用当前位置作为停止点
        }
      }

      if (shouldStop) {
        if (!anim.blockedLabel) {
          // 确定标签显示位置
          let labelPos: THREE.Vector3
          if (stopNode) {
            labelPos = new THREE.Vector3(stopNode.x, 0, stopNode.y)
          } else {
            labelPos = anim.mesh.position.clone()
          }

          const label = createBlockedLabel(labelPos)
          scene.add(label)
          anim.blockedLabel = label
          
          // 立即隐藏 Flow Mesh
          anim.mesh.visible = false

          // 停止动画并保持一段时间后移除
          setTimeout(() => {
            if (anim.mesh && anim.mesh.parent) {
              scene.remove(anim.mesh)
              anim.mesh.geometry.dispose()
              if (Array.isArray(anim.mesh.material)) {
                anim.mesh.material.forEach(m => m.dispose())
              } else {
                anim.mesh.material.dispose()
              }
            }
            if (anim.blockedLabel) {
              scene.remove(anim.blockedLabel)
              anim.blockedLabel.material.map?.dispose()
              anim.blockedLabel.material.dispose()
            }
            flowAnimations.delete(anim.id)
          }, 1000) // 停留1秒展示 BLOCKED
        }
        
        return
      }
    }

    if (anim.progress >= 1 && !anim.blocked) {
      return
    }

    const pathLength = anim.path.length
    if (pathLength < 2) return

    const segmentProgress = anim.progress * (pathLength - 1)
    const segmentIndex = Math.floor(segmentProgress)
    const segmentT = segmentProgress - segmentIndex

    if (segmentIndex >= pathLength - 1) {
      const lastNode = anim.path[pathLength - 1]
      if (lastNode) {
        anim.mesh.position.set(lastNode.x, 0, lastNode.y)
        const scale = 1 - (anim.progress - (pathLength - 2) / (pathLength - 1)) * (pathLength - 1)
        anim.mesh.scale.set(scale, scale, scale)
      }
    } else {
      const startNode = anim.path[segmentIndex]
      const endNode = anim.path[segmentIndex + 1]

      if (startNode && endNode) {
        const x = startNode.x + (endNode.x - startNode.x) * segmentT
        const z = startNode.y + (endNode.y - startNode.y) * segmentT
        anim.mesh.position.set(x, 0, z)

        let scale = 1
        if (anim.progress < 0.1) {
          scale = anim.progress / 0.1
        } else if (anim.progress > 0.9) {
          scale = (1 - anim.progress) / 0.1
        }
        anim.mesh.scale.set(scale, scale, scale)
      }
    }
  })
}

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.hostname
  const port = 8766
  const url = `${protocol}://${host}:${port}/ui-events`

  ws = new WebSocket(url)

  ws.onopen = () => {
    // WebSocket connected
  }

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as UiEventItem
      if (data && data.type && data.data) {
        const eventType = data.type.toLowerCase()
        const eventData = data.data

        // 处理节点状态更新
        if (eventType === 'network_status_update') {
          const nodeId = eventData.node_id
          const status = eventData.status
          const nodeObj = nodeObjects.get(nodeId)
          if (nodeObj) {
            nodeObj.data.status = status
            // 如果当前选中了该节点，更新详情面板
            if (selectedNode.value && selectedNode.value.id === nodeId) {
              selectedNode.value = { ...nodeObj.data }
            }
            // 更新 3D 场景中的节点颜色（如果有状态颜色映射）
            // updateNodeVisuals(nodeObj) // 假设有这个函数，或者直接修改 mesh
          }
        }

        // 处理节点指标更新
        if (eventType === 'node_metrics_update') {
          const nodeId = eventData.node_id
          const metrics = eventData.metrics
          const nodeObj = nodeObjects.get(nodeId)
          if (nodeObj) {
            nodeObj.data.metrics = metrics
            // 如果当前选中了该节点，更新详情面板
            if (selectedNode.value && selectedNode.value.id === nodeId) {
              selectedNode.value = { ...nodeObj.data }
            }
          }
        }

        if (eventType.includes('flow') || eventType.includes('traffic') || eventType.includes('packet')) {
          let sourceId = eventData.source || eventData.src || eventData.from
          let targetId = eventData.target || eventData.dst || eventData.to
          let pathHops = eventData.path_hops
          let blocked = eventData.blocked

          // 如果没有直接的节点 ID，尝试从 flow 对象中提取
          if (!sourceId || !targetId) {
            const flow = eventData.flow || eventData
            const srcIp = flow.src_ip || eventData.src_ip
            const dstIp = flow.dst_ip || eventData.dst_ip
            if (!pathHops) {
              pathHops = flow.path_hops
            }
            if (blocked === undefined) {
              blocked = flow.blocked
            }

            // 通过 IP 地址查找节点 ID
            if (srcIp) {
              for (const [nodeId, nodeObj] of nodeObjects) {
                if (nodeObj.data.ip === srcIp) {
                  sourceId = nodeId
                  break
                }
              }
            }
            if (dstIp) {
              for (const [nodeId, nodeObj] of nodeObjects) {
                if (nodeObj.data.ip === dstIp) {
                  targetId = nodeId
                  break
                }
              }
            }
          }

          if (sourceId && targetId && nodeObjects.has(sourceId) && nodeObjects.has(targetId)) {
            createFlowAnimation(sourceId, targetId, pathHops, blocked)
          }
        }
      }
    } catch (err) {
      console.error('解析 WS 消息失败', err)
    }
  }

  ws.onclose = () => {
    setTimeout(() => {
      connectWebSocket()
    }, 1000)
  }

  ws.onerror = (err) => {
    console.error('Topology WS error', err)
  }
}

const onWindowResize = () => {
  if (!containerRef.value || !camera || !renderer) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  const aspect = width / height

  camera.aspect = aspect
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

const onMouseDown = (event: MouseEvent) => {
  if (event.button !== 0) return
  if (!containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(scene.children, true)

  let clickedNode: NodeObject | null = null

  for (let i = 0; i < intersects.length; i++) {
    const intersect = intersects[i]
    if (!intersect) continue
    let obj: THREE.Object3D | null = intersect.object

    let depth = 0
    while (obj && (!obj.userData || !obj.userData.isNode) && depth < 10) {
      obj = obj.parent
      depth++
    }

    if (obj && obj.userData && obj.userData.isNode) {
      const nodeId = obj.userData.id
      clickedNode = nodeObjects.get(nodeId) || null
      break
    }
  }

  if (clickedNode) {
    draggedNode = clickedNode
    isDraggingNode = true
    dragStartMouse.set(event.clientX, event.clientY)
    controls.enabled = false
    if (simulation) {
      simulation.alphaTarget(0.3).restart()
    }
    document.body.style.cursor = 'grabbing'
  } else {
    dragStart.set(event.clientX, event.clientY)
    isDragging = true
    document.body.style.cursor = 'grabbing'
  }
}

const onMouseUp = (event: MouseEvent) => {
  if (isDraggingNode && draggedNode) {
    const dragDistance = Math.sqrt(
      Math.pow(event.clientX - dragStartMouse.x, 2) +
      Math.pow(event.clientY - dragStartMouse.y, 2)
    )

    if (dragDistance < 5) {
      selectNode(draggedNode.data)
      selectLink(null)
    }

    if (simulation) {
      draggedNode.fx = undefined
      draggedNode.fy = undefined
      simulation.alphaTarget(0)
    }

    draggedNode = null
    isDraggingNode = false
    controls.enabled = true
  }

  isDragging = false
  document.body.style.cursor = 'default'
}

const onMouseWheel = (event: WheelEvent) => {
  event.preventDefault()

  const delta = event.deltaY
  const zoomSpeed = 50
  const newHeight = cameraOffset.y + delta * zoomSpeed * 0.01

  cameraOffset.y = Math.max(CONFIG.cameraMinHeight, Math.min(CONFIG.cameraMaxHeight, newHeight))

  camera.position.set(cameraOffset.x, cameraOffset.y, cameraOffset.z)
  camera.lookAt(cameraOffset.x, 0, cameraOffset.z)
}

const onMouseMove = (event: MouseEvent) => {
  if (!containerRef.value) return

  if (isDraggingNode && draggedNode) {
    const rect = containerRef.value.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    raycaster.setFromCamera(mouse, camera)
    const target = new THREE.Vector3()
    raycaster.ray.intersectPlane(dragPlane, target)

    if (target) {
      draggedNode.fx = target.x
      draggedNode.fy = target.z
      draggedNode.x = target.x
      draggedNode.y = target.z

      if (simulation) {
        simulation.alphaTarget(0.3).restart()
      }
    }
    return
  }

  if (isDragging) {
    const deltaX = (event.clientX - dragStart.x) * 2
    const deltaY = (event.clientY - dragStart.y) * 2

    cameraOffset.x -= deltaX
    cameraOffset.z -= deltaY

    camera.position.set(cameraOffset.x, cameraOffset.y, cameraOffset.z)
    camera.lookAt(cameraOffset.x, 0, cameraOffset.z)

    dragStart.set(event.clientX, event.clientY)
    return
  }

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(scene.children, true)

  let foundNode = false
  let foundLink = false
  let currentHoveredLink: LinkObject | null = null
  let currentHoveredNode: NodeObject | null = null

  for (const intersect of intersects) {
    let obj: THREE.Object3D | null = intersect.object

    if (obj && obj.userData && obj.userData.isLink) {
      const link = linkObjects.find(l => l.threeMesh === obj)
      if (link) {
        currentHoveredLink = link
        foundLink = true
        break
      }
    }

    while (obj && (!obj.userData || !obj.userData.isNode)) {
      obj = obj.parent
    }

    if (obj && obj.userData && obj.userData.isNode) {
      const nodeId = obj.userData.id
      const nodeObj = nodeObjects.get(nodeId)
      if (nodeObj) {
        currentHoveredNode = nodeObj
        showTooltip(event, nodeObj.data)
        foundNode = true
        break
      }
    }
  }

  // 恢复之前高亮的 Link
  if (hoveredLink && hoveredLink !== currentHoveredLink) {
    if (selectedLink.value && hoveredLink === selectedLink.value) {
      hoveredLink.threeMesh.scale.x = 4
      hoveredLink.threeMesh.scale.y = 4
    } else {
      hoveredLink.threeMesh.scale.x = 1
      hoveredLink.threeMesh.scale.y = 1
    }
  }

  // 恢复之前高亮的 Node
  if (hoveredNode && hoveredNode !== currentHoveredNode) {
    hoveredNode.threeGroup.children.forEach(child => {
      if (child instanceof THREE.LineSegments) {
        const mat = child.material as THREE.LineBasicMaterial
        if (child.userData.isCorner) {
          mat.linewidth = 3.5
        } else {
          mat.linewidth = 2
        }
      }
    })
  }

  // 高亮当前 Link
  if (currentHoveredLink) {
    if (selectedLink.value && currentHoveredLink === selectedLink.value) {
      currentHoveredLink.threeMesh.scale.x = 4
      currentHoveredLink.threeMesh.scale.y = 4
    } else {
      currentHoveredLink.threeMesh.scale.x = 3
      currentHoveredLink.threeMesh.scale.y = 3
    }

    const source = currentHoveredLink.source as NodeObject
    const target = currentHoveredLink.target as NodeObject
    showLinkTooltip(event, currentHoveredLink.data, source.data, target.data)

    document.body.style.cursor = 'pointer'
    hoveredLink = currentHoveredLink
  } else if (currentHoveredNode) {
    // 高亮当前 Node
    currentHoveredNode.threeGroup.children.forEach(child => {
      if (child instanceof THREE.LineSegments) {
        const mat = child.material as THREE.LineBasicMaterial
        if (child.userData.isCorner) {
          mat.linewidth = 5
        } else {
          mat.linewidth = 3
        }
      }
    })
    const nodeData = currentHoveredNode.data
    showTooltip(event, nodeData)
    document.body.style.cursor = 'pointer'
    hoveredNode = currentHoveredNode
  } else {
    if (!foundNode && !foundLink) {
      hideTooltip()
      document.body.style.cursor = 'default'
    }
    hoveredLink = null
    hoveredNode = null
  }
}

const onMouseClick = (event: MouseEvent) => {
  if (isDragging || isDraggingNode) return
  if (!containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(scene.children, true)

  for (let i = 0; i < intersects.length; i++) {
    const intersect = intersects[i]
    if (!intersect) continue
    let obj: THREE.Object3D | null = intersect.object

    if (obj && obj.userData && obj.userData.isLink) {
      const link = linkObjects.find(l => l.threeMesh === obj)
      if (link) {
        selectLink(link)
        return
      }
    }

    let depth = 0
    while (obj && (!obj.userData || !obj.userData.isNode) && depth < 10) {
      obj = obj.parent
      depth++
    }

    if (obj && obj.userData && obj.userData.isNode) {
      const nodeId = obj.userData.id
      const nodeObj = nodeObjects.get(nodeId)
      if (nodeObj) {
        selectNode(nodeObj.data)
        selectLink(null)
        return
      }
    }
  }
}

const selectLink = (link: LinkObject | null) => {
  if (selectedLink.value && selectedLink.value !== link) {
    selectedLink.value.threeMesh.scale.x = 1
    selectedLink.value.threeMesh.scale.y = 1
  }

  selectedLink.value = link
  if (link) {
    selectedNode.value = null
    if (selectedHighlight.group) {
      scene.remove(selectedHighlight.group)
      selectedHighlight.group = null
    }
    link.threeMesh.scale.x = 4
    link.threeMesh.scale.y = 4
  }
}

const getMetricColor = (val: number) => {
  if (val > 80) return '#FF2A6D'
  if (val > 50) return '#FFA500'
  return '#00FF9C'
}

const selectNode = (node: TopologyNode | null) => {
  selectedNode.value = node

  if (selectedHighlight.group) {
    scene.remove(selectedHighlight.group)
    selectedHighlight.group = null
  }

  if (node) {
    const nodeObj = nodeObjects.get(node.id)
    if (nodeObj) {
      const highlightSize = CONFIG.nodeSize * 1.2
      const highlightHeight = highlightSize * CONFIG.heightRatio
      const cornerLength = highlightSize * 0.15

      const highlightMat = new THREE.LineBasicMaterial({
        color: 0xffffff,
        linewidth: 4,
        transparent: true,
        opacity: 1
      })
      const highlightCorners = createTopBottomCornerWireframe(highlightSize, highlightHeight, cornerLength, highlightMat)

      const highlightGroup = new THREE.Group()
      highlightGroup.add(highlightCorners)
      highlightGroup.position.copy(nodeObj.threeGroup.position)
      scene.add(highlightGroup)

      selectedHighlight.group = highlightGroup
    }
  }
}

const showTooltip = (event: MouseEvent, data: TopologyNode) => {
  const statusColor = CONFIG.statusColors[data.status || 'unknown']
  const typeColor = CONFIG.colors[data.type.toLowerCase()] || '#fff'

  tooltipContent.value = `
    <div class="cyber-tooltip-content">
      <div class="header" style="border-bottom: 2px solid ${typeColor}">
        <span class="title">>> ${data.name}</span>
        <span class="type" style="background-color:${typeColor}; color:#000000">${data.type.toUpperCase()}</span>
      </div>
      <div class="body">
        <div class="row"><span class="label">ID:</span> <span class="value">${data.id}</span></div>
        <div class="row"><span class="label">IP:</span> <span class="value active">${data.ip || 'N/A'}</span></div>
        <div class="row">
          <span class="label">STATUS:</span> 
          <span class="value status-tag" style="background-color:${statusColor}; color:#000000">
            ${data.status?.toUpperCase() || 'UNKNOWN'}
          </span>
        </div>
      </div>
    </div>
  `

  tooltipPos.value = { x: event.clientX + 15, y: event.clientY + 15 }
  tooltipVisible.value = true
}

const showLinkTooltip = (event: MouseEvent, linkData: TopologyLink, sourceData: TopologyNode, targetData: TopologyNode) => {
  const statusColor = CONFIG.statusColors[linkData.status || 'unknown']

  tooltipContent.value = `
    <div class="cyber-tooltip-content">
      <div class="header" style="border-bottom: 2px solid #FFFFFF">
        <span class="title">>> LINK</span>
      </div>
      <div class="body">
        <div class="row"><span class="label">FROM:</span> <span class="value">${sourceData.name}</span></div>
        <div class="row"><span class="label">TO:</span> <span class="value">${targetData.name}</span></div>
        <div class="row">
          <span class="label">STATUS:</span> 
          <span class="value status-tag" style="background-color:${statusColor}; color:#000000">
            ${linkData.status?.toUpperCase() || 'UNKNOWN'}
          </span>
        </div>
        ${linkData.bandwidth ? `<div class="row"><span class="label">BANDWIDTH:</span> <span class="value active">${linkData.bandwidth}</span></div>` : ''}
      </div>
    </div>
  `

  tooltipPos.value = { x: event.clientX + 15, y: event.clientY + 15 }
  tooltipVisible.value = true
}

const hideTooltip = () => {
  tooltipVisible.value = false
}

const updateSpriteScales = () => {
  // 根据摄像机距离动态调整 Sprite 大小，使其在屏幕上保持相对固定大小
  if (!containerRef.value) return

  nodeObjects.forEach(nodeObj => {
    nodeObj.threeGroup.children.forEach(child => {
      if (child instanceof THREE.Sprite && child.userData.isLabel) {
        const distance = camera.position.distanceTo(nodeObj.threeGroup.position)
        // 基础缩放系数，根据实际效果调整
        const scaleFactor = distance * 0.002
        const baseScale = child.userData.baseScale
        child.scale.set(baseScale.x * scaleFactor, baseScale.y * scaleFactor, 1)
      }
    })
  })
}

const animate = () => {
  animationId = requestAnimationFrame(animate)
  controls.update()
  camera.position.y = cameraOffset.y
  camera.lookAt(camera.position.x, 0, camera.position.z)

  updateFlowAnimations()
  updateSpriteScales()

  renderer.render(scene, camera)
}
const loadTopology = async () => {
  loading.value = true
  try {
    const data = await fetchTopology()
    topologyData.value = data
    if (data) {
      updateTopology(data)
    }
  } catch (error: any) {
    ElMessage.error(`加载拓扑数据失败: ${error.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  loadTopology()
}


onMounted(() => {
  initThree()
  loadTopology()
  connectWebSocket()
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
  if (simulation) simulation.stop()
  if (ws) {
    ws.close()
    ws = null
  }
  if (renderer) {
    renderer.domElement.removeEventListener('wheel', onMouseWheel)
    renderer.dispose()
  }
  window.removeEventListener('resize', onWindowResize)
})
</script>

<template>
  <div class="topology-container cyber-grid-bg">
    <div class="top-toolbar">
      <span class="cyber-title">网络拓扑视图 // 3D MAP VIEW</span>
      <div class="header-actions">
        <el-button type="primary" :icon="Refresh" @click="refresh" :loading="loading" class="cyber-btn">
          REFRESH
        </el-button>
      </div>
    </div>

    <div ref="containerRef" class="topology-chart-wrapper scanline"></div>

    <div v-show="tooltipVisible" ref="tooltipRef" class="cyber-tooltip"
      :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }" v-html="tooltipContent"></div>

    <div v-if="selectedNode" class="node-detail-panel">
      <div class="panel-header">
        <span class="panel-title">>> NODE DETAIL</span>
        <el-button text @click="selectNode(null)" class="close-btn" style="padding: 0; min-height: auto;">
          ×
        </el-button>
      </div>
      <div class="panel-content">
        <div class="detail-section">
          <div class="detail-row">
            <span class="detail-label">NAME:</span>
            <span class="detail-value">{{ selectedNode.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">ID:</span>
            <span class="detail-value code">{{ selectedNode.id }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">TYPE:</span>
            <span class="detail-value type-tag" :style="{
              backgroundColor: CONFIG.colors[selectedNode.type.toLowerCase()] || '#fff',
              color: '#000000'
            }">
              {{ selectedNode.type.toUpperCase() }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">IP:</span>
            <span class="detail-value active">{{ selectedNode.ip || 'N/A' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">STATUS:</span>
            <span class="detail-value status-tag" :style="{
              backgroundColor: CONFIG.statusColors[selectedNode.status || 'unknown'],
              color: '#000000'
            }">
              {{ (selectedNode.status || 'UNKNOWN').toUpperCase() }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">CONNECTIONS:</span>
            <span class="detail-value">{{ nodeObjects.get(selectedNode.id)?.degree || 0 }}</span>
          </div>
        </div>

        <div v-if="selectedNode.metrics" class="detail-section">
          <div class="section-title">REALTIME METRICS</div>
          <div class="detail-row">
            <span class="detail-label">CPU:</span>
            <div class="metric-bar-container">
              <div class="metric-bar"
                :style="{ width: (selectedNode.metrics.cpu_usage || 0) + '%', backgroundColor: getMetricColor(selectedNode.metrics.cpu_usage || 0) }">
              </div>
              <span class="metric-text">{{ (selectedNode.metrics.cpu_usage || 0).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="detail-row">
            <span class="detail-label">MEM:</span>
            <div class="metric-bar-container">
              <div class="metric-bar"
                :style="{ width: (selectedNode.metrics.memory_usage || 0) + '%', backgroundColor: getMetricColor(selectedNode.metrics.memory_usage || 0) }">
              </div>
              <span class="metric-text">{{ (selectedNode.metrics.memory_usage || 0).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="detail-row">
            <span class="detail-label">NET:</span>
            <span class="detail-value active">{{ (selectedNode.metrics.network_throughput || 0).toFixed(2) }}
              Mbps</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">CONNECTED NODES</div>
          <div class="connected-list">
            <div v-for="link in linkObjects.filter(l =>
              selectedNode && ((l.source as NodeObject).id === selectedNode.id ||
                (l.target as NodeObject).id === selectedNode.id)
            )" :key="`${(link.source as NodeObject).id}-${(link.target as NodeObject).id}`" class="connected-item">
              <span class="connected-name">
                {{ selectedNode && (link.source as NodeObject).id === selectedNode.id
                  ? (link.target as NodeObject).data.name
                  : (link.source as NodeObject).data.name }}
              </span>
              <span class="connected-status" :class="link.data.status?.toLowerCase()">
                {{ link.data.status || 'UNKNOWN' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="selectedLink" class="node-detail-panel">
      <div class="panel-header">
        <span class="panel-title">>> LINK DETAIL</span>
        <el-button text @click="selectLink(null)" class="close-btn" style="padding: 0; min-height: auto;">
          ×
        </el-button>
      </div>
      <div class="panel-content">
        <div class="detail-section">
          <div class="detail-row">
            <span class="detail-label">FROM:</span>
            <span class="detail-value">{{ (selectedLink.source as NodeObject).data.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">FROM ID:</span>
            <span class="detail-value code">{{ selectedLink.data.source }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">TO:</span>
            <span class="detail-value">{{ (selectedLink.target as NodeObject).data.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">TO ID:</span>
            <span class="detail-value code">{{ selectedLink.data.target }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">STATUS:</span>
            <span class="detail-value status-tag" :style="{
              backgroundColor: CONFIG.statusColors[selectedLink.data.status || 'unknown'],
              color: '#000000'
            }">
              {{ (selectedLink.data.status || 'UNKNOWN').toUpperCase() }}
            </span>
          </div>
          <div v-if="selectedLink.data.bandwidth" class="detail-row">
            <span class="detail-label">BANDWIDTH:</span>
            <span class="detail-value active">{{ selectedLink.data.bandwidth }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">SOURCE NODE</div>
          <div class="detail-row">
            <span class="detail-label">TYPE:</span>
            <span class="detail-value type-tag" :style="{
              backgroundColor: CONFIG.colors[(selectedLink.source as NodeObject).data.type.toLowerCase()] || '#fff',
              color: '#000000'
            }">
              {{ (selectedLink.source as NodeObject).data.type.toUpperCase() }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">IP:</span>
            <span class="detail-value active">{{ (selectedLink.source as NodeObject).data.ip || 'N/A' }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">TARGET NODE</div>
          <div class="detail-row">
            <span class="detail-label">TYPE:</span>
            <span class="detail-value type-tag" :style="{
              backgroundColor: CONFIG.colors[(selectedLink.target as NodeObject).data.type.toLowerCase()] || '#fff',
              color: '#000000'
            }">
              {{ (selectedLink.target as NodeObject).data.type.toUpperCase() }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">IP:</span>
            <span class="detail-value active">{{ (selectedLink.target as NodeObject).data.ip || 'N/A' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topology-container {
  padding: 0;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: var(--cyber-bg);
  overflow: hidden;
}

.top-toolbar {
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--cyber-header-bg);
  border-bottom: var(--cyber-border-primary);
  z-index: 10;
}

.topology-chart-wrapper {
  flex: 1;
  width: 100%;
  position: relative;
  background-color: var(--cyber-dot-bg);
  background-image: radial-gradient(var(--cyber-dot-color) 1px, transparent 1px);
  background-size: 20px 20px;
  overflow: hidden;
}

.cyber-tooltip {
  position: fixed;
  z-index: 9999;
  pointer-events: none;
  background: var(--cyber-card-bg);
  border: var(--cyber-border-primary);
  padding: 12px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
  font-family: '0xProto Nerd Font', monospace;
  min-width: 200px;
  transform: translate(10px, 10px);
  backdrop-filter: blur(4px);
}

:deep(.cyber-tooltip-content .header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: var(--cyber-border-primary);
}

:deep(.cyber-tooltip-content .title) {
  color: var(--cyber-text-main);
  font-weight: bold;
  font-size: 14px;
}

:deep(.cyber-tooltip-content .type) {
  font-size: 10px;
  font-weight: bold;
}

:deep(.cyber-tooltip-content .row) {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--cyber-text-sub);
}

:deep(.cyber-tooltip-content .value.active) {
  color: var(--cyber-secondary);
}

:deep(.cyber-tooltip-content .status-tag) {
  padding: 2px 6px;
  font-size: 10px;
  font-weight: bold;
  display: inline-block;
}

:deep(.cyber-tooltip-content .type) {
  padding: 2px 6px;
  font-size: 10px;
  font-weight: bold;
  display: inline-block;
}

.node-detail-panel {
  position: fixed;
  right: 20px;
  top: 80px;
  bottom: 20px;
  width: 320px;
  background: var(--cyber-card-bg);
  border: var(--cyber-border-primary);
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  font-family: '0xProto Nerd Font', monospace;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  border-bottom: var(--cyber-border-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--cyber-table-header-bg);
}

.panel-title {
  color: var(--cyber-text-main);
  font-size: 14px;
  font-weight: bold;
  letter-spacing: 1px;
}

.close-btn {
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.2s;
  color: var(--cyber-text-main);
}

.close-btn:hover {
  color: #FF2A6D !important;
}

.panel-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: 24px;
}

.section-title {
  color: var(--cyber-text-sub);
  font-size: 11px;
  font-weight: bold;
  margin-bottom: 12px;
  letter-spacing: 1px;
  border-bottom: var(--cyber-border-primary);
  padding-bottom: 6px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
}

.detail-label {
  color: var(--cyber-text-sub);
  font-weight: bold;
  min-width: 100px;
}

.detail-value {
  color: var(--cyber-text-main);
  text-align: right;
  flex: 1;
}

.detail-value.code {
  font-family: '0xProto Nerd Font', monospace;
  font-size: 10px;
  color: var(--cyber-topo-active);
  word-break: break-all;
}

.detail-value.active {
  color: var(--cyber-topo-active);
}

.detail-value.type-tag,
.detail-value.status-tag {
  padding: 2px 8px;
  font-size: 10px;
  display: inline-block;
  font-weight: bold;
}

.metric-bar-container {
  flex: 1;
  height: 12px;
  background: rgba(255, 255, 255, 0.1);
  position: relative;
  margin-left: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.metric-bar {
  height: 100%;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.metric-text {
  position: absolute;
  right: 4px;
  top: -2px;
  font-size: 9px;
  color: #fff;
  text-shadow: 1px 1px 2px #000;
  font-weight: bold;
}
.connected-list {
  max-height: 300px;
  overflow-y: auto;
}

.connected-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  margin-bottom: 6px;
  background: var(--cyber-table-header-bg);
  border: var(--cyber-border-primary);
  font-size: 11px;
}

.connected-name {
  color: var(--cyber-text-main);
  flex: 1;
}

.connected-status {
  padding: 2px 6px;
  font-size: 9px;
  border: 1px solid;
}

.connected-status.online {
  color: var(--cyber-text-main);
  border-color: var(--cyber-border-color);
}

.connected-status.offline {
  color: #909399;
  border-color: #909399;
}

.connected-status.error {
  color: #FF2A6D;
  border-color: #FF2A6D;
}

.connected-status.warning {
  color: #FFE600;
  border-color: #FFE600;
}

.node-label {
  position: absolute;
  pointer-events: none;
  user-select: none;
  z-index: 1000;
}
</style>