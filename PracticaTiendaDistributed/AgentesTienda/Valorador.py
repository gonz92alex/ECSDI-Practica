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

from __future__ import print_function

import argparse
from multiprocessing import Process, Queue
import socket

from rdflib import Namespace, Graph, logger, RDF, URIRef
from flask import Flask, request

from PracticaTienda.utils.ACLMessages import register_agent, get_message_properties, build_message, get_agent_info, \
    send_message
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.OntoNamespaces import ACL
from PracticaTienda.utils.OntologyNamespaces import ECSDI

__author__ = 'Amazon V2'

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
    port = 9010
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

AgenteComprador = Agent('AgenteComprador',
                        agn.AgenteComprador,
                        'http://%s:%d/comm' % (hostname, port),
                        'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')


def get_n_message():
    global messages_cnt
    messages_cnt += messages_cnt
    return messages_cnt


def register_message():
    logger.info('Registrando Agente Comprador...')
    gr = register_agent(AgenteComprador, DirectoryAgent, AgenteComprador.uri, get_n_message())


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    gr = None
    logger.info('Peticion de info recibida')

    # Extraemos el mensaje que nos envian
    mensaje = request.args['content']
    gm = Graph()
    gm.parse(data=mensaje)

    msgdic = get_message_properties(gm)

    # Comprobacion del mensaje

    if msgdic is None:
        gr = build_message(Graph(), ACL['no_entendido'], sender=AgenteComprador.uri, msgcnt=get_n_message())
    else:
        performative = msgdic['performative']

        if performative != ACL.request:
            gr = build_message(Graph(), ACL['no_entendido'], sender=AgenteComprador.uri, msgcnt=get_n_message())

        else:
            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)
            logger.info('Recibida una petición en AgenteComprador')
            if accion == ECSDI.Peticion_compra:
                logger.info('Recibida peticion compra')
                compra = None
                for item in gm.subjects(RDF.type, ECSDI.Compra):
                    compra = item

                gm.remove((content, None, None))
                for item in gm.subjects(RDF.type, ACL.FipaAclMessage):
                    gm.remove((item, None, None))

                registerSells(gm)
                payDelivery(compra)
                logger.info('Envio la factura de la venda con id ' + compra + 'al usuario comprador.')
                gr = sendSell(gm, compra)

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


def payDelivery(compra_url):
    logger.info('Se acepta la transferencia de' + compra_url)


def registerSells(gm):
    ontologyFile = open('../Datos/Compras')

    g = Graph()
    g.parse(ontologyFile, format='turtle')
    g += gm

    # Guardem el graf
    g.serialize(destination='../Datos/Compras', format='turtle')
    return g


def sendSell(gm, sell):

    logger.info('Nos comunicamos con el Centro Logistico')
    content = ECSDI['Enviar_venta_' + str(get_n_message())]

    gm.add((content, RDF.type, ECSDI.Enviar_venta))
    gm.add((content, ECSDI.identificador_Compra, URIRef(sell)))

    centro_logistico = get_agent_info(agn.AgenteCentroLogistico, DirectoryAgent, AgenteComprador, get_n_message())

    gr = send_message(
        build_message(gm, perf=ACL.request, sender=AgenteComprador.uri, receiver=centro_logistico.uri,
                      msgcnt=get_n_message(),
                      content=content), centro_logistico.address)
    return gr
    pass


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
