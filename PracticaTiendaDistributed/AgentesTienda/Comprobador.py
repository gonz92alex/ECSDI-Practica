# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""
import argparse
import datetime
import random
import socket
import sys
from Queue import Queue
from multiprocessing import Process

from flask import Flask, request
from rdflib import Namespace, Graph, logger, RDF, Literal, XSD, URIRef

from PracticaTienda.utils.ACLMessages import register_agent, build_message, get_message_properties, get_agent_info, \
    send_message
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.OntologyNamespaces import ECSDI, ACL

__author__ = 'ECSDIshop'

parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default=socket.gethostname(), help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--host', default=socket.gethostname(), help="Host del agente")


args = parser.parse_args()
# Configuration stuff
if args.port is None:
    port = 9004
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = args.host

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente

AgenteCentroLogistico = Agent('AgenteCentroLogistico',
                       agn.AgenteCentroLogistico,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__,template_folder='../templates')

def get_n_message():
    global messages_cnt
    messages_cnt += messages_cnt
    return messages_cnt


def register_message():
    logger.info("Registrando Agente CentroLogistico...")
    gr = register_agent(AgenteCentroLogistico, DirectoryAgent, AgenteCentroLogistico.uri, get_n_message())


@app.route("/comm")
def communication():
    global dsgraph
    gr = None

    logger.info('Peticion de informacion recibida')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCentroLogistico.uri, msgcnt=get_n_message())
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=AgenteCentroLogistico.uri, msgcnt=get_n_message())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro

            # Averiguamos el tipo de la accion
            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)

            # Aqui realizariamos lo que pide la accion

            if accion == ECSDI.Enviar_venta:
                logger.info('Recibimos la peticion para enviar la venta')
                products = obtainProducts(gm)
                gr = create_and_sendProducts(products)

            elif accion == ECSDI.Recoger_devolucion:
                logger.info('Recibimos la peticion de recoger la devolucion, para ello contratamos un envio')
                date = dateToMillis(datetime.datetime.utcnow() + datetime.timedelta(days=9))
                for item in gm.objects(subject=content, predicate=ECSDI.compra_a_devolver):
                    peso = crearEnvio(item, date)
                    requestTransport(date, peso)
                    logger.info('Eliminamos la venta de nuestro registro')
                    ventas = Graph()
                    ventas.parse(open('../Datos/Compras'), format='turtle')
                    ventas.remove((item, None, None))
                    ventas.serialize(destination='../Datos/Compras', format='turtle')

                gr = Graph()



            else:
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=DirectoryAgent.uri,
                                   msgcnt=get_n_message())

    logger.info('Respondemos a la peticion')

    return gr.serialize(format='xml'), 200
    pass


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"

#--------------------------PARA ENVIAR PRODUCTOS------------------------------------------
def create_and_sendProducts(gr):
    logger.info('Enviamos los productos')

    content = ECSDI['Enviar_lot' + str(get_n_message())]
    gr.add((content, RDF.type, ECSDI.Enviar_lot))

    subjectLoteProducto = ECSDI['Lote_producto' + str(random.randint(1, sys.float_info.max))]
    gr.add((subjectLoteProducto, RDF.type, ECSDI.Lote_producto))
    gr.add((subjectLoteProducto, ECSDI.Prioridad, Literal(1, datatype=XSD.integer)))

    for item in gr.subjects(RDF.type, ECSDI.Producto):
        gr.add((subjectLoteProducto, ECSDI.productos, URIRef(item)))

    gr.add((content, ECSDI.a_enviar, URIRef(subjectLoteProducto)))

    # Se ha creado el envio de un lato de productos, ahora se procedede a negociar el envio y enviarlo
    logger.info('Se envia el lote de productos')
    date = dateToMillis(datetime.datetime.utcnow() + datetime.timedelta(days=9))
    urlEnvio = writeSends(gr, date)
    peso = obtenerPesoTotal(urlEnvio)
    requestTransport(date, peso)
    gr = prepareSellResponse(urlEnvio)
    return gr

def obtainProducts(gm):
    products = Graph()

    sell = None
    for item in gm.subjects(RDF.type, ECSDI.Compra):
        sell = item

    sellsGraph = Graph()
    sellsGraph.parse(open('../Datos/Compras'), format='turtle')

    for item in sellsGraph.objects(sell, ECSDI.Productos):
        marca = sellsGraph.value(subject=item, predicate=ECSDI.Marca)
        nombre = sellsGraph.value(subject=item, predicate=ECSDI.Nombre)
        modelo = sellsGraph.value(subject=item, predicate=ECSDI.Modelo)
        precio = sellsGraph.value(subject=item, predicate=ECSDI.Precio)
        peso = sellsGraph.value(subject=item, predicate=ECSDI.Peso)
        products.add((item, RDF.type, ECSDI.Producto))
        products.add((item, ECSDI.Marca, Literal(marca, datatype=XSD.string)))
        products.add((item, ECSDI.Nombre, Literal(nombre, datatype=XSD.string)))
        products.add((item, ECSDI.Modelo, Literal(modelo, datatype=XSD.string)))
        products.add((item, ECSDI.Precio, Literal(precio, datatype=XSD.float)))
        products.add((item, ECSDI.Peso, Literal(peso, datatype=XSD.float)))

    return products


def obtenerPesoTotal(urlEnvio):
    peso_Total = 0.0

    gSends = Graph()
    gSends.parse(open('../Datos/Envios'), format='turtle')
    productsArray = []
    for lote in gSends.objects(subject=urlEnvio, predicate=ECSDI.Envia):
        for producto in gSends.objects(subject=lote, predicate=ECSDI.productos):
            productsArray.append(producto)


    gProducts = Graph()
    gProducts.parse(open('../Datos/productos'), format='turtle')
    for item in productsArray:
        peso_Total += float(gProducts.value(subject=item, predicate=ECSDI.Peso))

    return peso_Total


def dateToMillis(date):
    return (date - datetime.datetime.utcfromtimestamp(0)).total_seconds() * 1000.0


def writeSends(gr, deliverDate):
    subjectEnvio = ECSDI['Envio_' + str(random.randint(1, sys.float_info.max))]

    gr.add((subjectEnvio, RDF.type, ECSDI.Envio))
    gr.add((subjectEnvio, ECSDI.Fecha_de_entrega, Literal(deliverDate, datatype=XSD.float)))
    for item in gr.subjects(RDF.type, ECSDI.Lote_producto):
        gr.add((subjectEnvio, ECSDI.Envia, URIRef(item)))

    g = Graph()
    gr += g.parse(open('../Datos/Envios'), format='turtle')

    gr.serialize(destination='../Datos/Envios', format='turtle')

    return subjectEnvio

def requestTransport(date, peso):
    logger.info('Pedimos el transporte')

    # Content of the message
    content = ECSDI['Peticion_de_transporte_' + str(get_n_message())]

    # Graph creation
    gr = Graph()
    gr.add((content, RDF.type, ECSDI.Peticion_Transporte))

    # Anadir fecha y peso
    gr.add((content, ECSDI.Fecha, Literal(date, datatype=XSD.float)))
    gr.add((content, ECSDI.Peso_envio, Literal(peso, datatype=XSD.float)))

    Negociador = get_agent_info(agn.AgenteNegociador, DirectoryAgent, AgenteCentroLogistico, get_n_message())

    gr = send_message(
        build_message(gr, perf=ACL.request, sender=AgenteCentroLogistico.uri, receiver=Negociador.uri,
                      msgcnt=get_n_message(),
                      content=content), Negociador.address)


def prepareSellResponse(urlEnvio):
    g = Graph()

    enviaments = Graph()
    enviaments.parse(open('../Datos/Envios'), format='turtle')

    urlProducts = []
    for item in enviaments.objects(subject=urlEnvio, predicate=ECSDI.Envia):
        for product in enviaments.objects(subject=item, predicate=ECSDI.productos):
            urlProducts.append(product)

    products = Graph()
    products.parse(open('../Datos/productos'), format='turtle')

    for item in urlProducts:
        marca = products.value(subject=item, predicate=ECSDI.Marca)
        modelo = products.value(subject=item, predicate=ECSDI.Modelo)
        nombre = products.value(subject=item, predicate=ECSDI.Nombre)
        precio = products.value(subject=item, predicate=ECSDI.Precio)

        g.add((item, RDF.type, ECSDI.Producto))
        g.add((item, ECSDI.Marca, Literal(marca, datatype=XSD.string)))
        g.add((item, ECSDI.Modelo, Literal(modelo, datatype=XSD.string)))
        g.add((item, ECSDI.Precio, Literal(precio, datatype=XSD.float)))
        g.add((item, ECSDI.Nombre, Literal(nombre, datatype=XSD.string)))

    return g


#--------------------------------------PARA LA DEVOLUCION DE PRODUCTOS-----------------------------------------------
def crearEnvio(sellUrl, date):
    enviarGrafo = Graph()

    subjectEnvio = ECSDI['Envio_' + str(random.randint(1, sys.float_info.max))]
    enviarGrafo.add((subjectEnvio, RDF.type, ECSDI.Envio))
    enviarGrafo.add((subjectEnvio, ECSDI.Fecha_de_entrega, Literal(date, datatype=XSD.float)))

    openGraph = Graph()
    openGraph.parse(open('../Datos/Compras'), format='turtle')

    subjectLote = ECSDI['Lote_producto' + str(random.randint(1, sys.float_info.max))]
    enviarGrafo.add((subjectLote, RDF.type, ECSDI.Lote_producto))
    enviarGrafo.add((subjectLote, ECSDI.Prioridad, Literal(1, datatype=XSD.integer)))

    peso = 0.0
    for item in openGraph.objects(subject=sellUrl, predicate=ECSDI.Productos):
        marca = openGraph.value(subject=item, predicate=ECSDI.Marca)
        modelo = openGraph.value(subject=item, predicate=ECSDI.Modelo)
        nombre = openGraph.value(subject=item, predicate=ECSDI.Nombre)
        precio = openGraph.value(subject=item, predicate=ECSDI.Precio)
        peso = openGraph.value(subject=item, predicate=ECSDI.Peso)
        peso += float(peso)

        enviarGrafo.add((item, RDF.type, ECSDI.Producto))
        enviarGrafo.add((item, ECSDI.Nombre, Literal(nombre, datatype=XSD.string)))
        enviarGrafo.add((item, ECSDI.Marca, Literal(marca, datatype=XSD.string)))
        enviarGrafo.add((item, ECSDI.Modelo, Literal(modelo, datatype=XSD.string)))
        enviarGrafo.add((item, ECSDI.Peso, Literal(peso, datatype=XSD.float)))
        enviarGrafo.add((item, ECSDI.Precio, Literal(precio, datatype=XSD.float)))

        enviarGrafo.add((subjectLote, ECSDI.productos, URIRef(item)))

    enviarGrafo.add((subjectEnvio, ECSDI.Envia, URIRef(subjectLote)))

    g = Graph()
    enviarGrafo += g.parse(open('../Datos/Envios'), format='turtle')

    enviarGrafo.serialize(destination='../Datos/Envios', format='turtle')

    return peso





def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """
    register_message()
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=())
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')


