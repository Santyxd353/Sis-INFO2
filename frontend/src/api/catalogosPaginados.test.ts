import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import { cargarCatalogoPaginado } from './catalogosPaginados'

describe('cargarCatalogoPaginado', () => {
  let mock: MockAdapter
  beforeEach(() => { mock = new MockAdapter(axiosInstance) })
  afterEach(() => mock.restore())
  it('acepta next absoluto del backend detrás del proxy /api', async () => { mock.onGet('/proxy').reply(200,{count:2,next:'http://127.0.0.1:8000/api/proxy?page=2',results:[{id:1}]}); mock.onGet('/api/proxy?page=2').reply(200,{count:2,next:null,results:[{id:2}]}); expect(await cargarCatalogoPaginado<{id:number}>('/proxy')).toEqual([{id:1},{id:2}]) })
  it('acepta una página y respuestas heredadas array', async () => { mock.onGet('/uno').reply(200,{count:1,next:null,results:[{id:1}]}); expect(await cargarCatalogoPaginado<{id:number}>('/uno')).toEqual([{id:1}]); mock.reset(); mock.onGet('/array').reply(200,[{id:2}]); expect(await cargarCatalogoPaginado<{id:number}>('/array')).toEqual([{id:2}]) })
  it('recorre next, conserva orden y elimina duplicados', async () => { mock.onGet('/pag').reply(200,{count:3,next:'/pag?page=2',results:[{id:1},{id:2}]}); mock.onGet('/pag?page=2').reply(200,{count:3,next:null,results:[{id:2},{id:3}]}); expect(await cargarCatalogoPaginado<{id:number}>('/pag')).toEqual([{id:1},{id:2},{id:3}]) })
  it('rechaza ciclos y otros orígenes', async () => { mock.onGet('/cycle').reply(200,{count:1,next:'/cycle',results:[]}); await expect(cargarCatalogoPaginado<{id:number}>('/cycle')).rejects.toThrow(/ciclo/); mock.reset(); mock.onGet('/other').reply(200,{count:1,next:'https://otro.test/p',results:[]}); await expect(cargarCatalogoPaginado<{id:number}>('/other')).rejects.toThrow(/origen/) })
  it('respeta AbortSignal y no impone page_size=100', async () => { const controller = new AbortController(); controller.abort(); await expect(cargarCatalogoPaginado<{id:number}>('/abort',undefined,controller.signal)).rejects.toMatchObject({name:'AbortError'}); mock.onGet('/many').reply((config) => [200,{count:101,next:null,results:[{id:101}], recibido:config.params}]); await cargarCatalogoPaginado<{id:number}>('/many'); expect(mock.history.get[0].params).not.toHaveProperty('page_size') })
})
